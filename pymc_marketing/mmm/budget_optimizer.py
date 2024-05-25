#   Copyright 2024 The PyMC Labs Developers
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
"""Budget optimization module."""

import warnings
from typing import Any

import numpy as np
from scipy.optimize import minimize

from pymc_marketing.mmm.components.adstock import AdstockTransformation
from pymc_marketing.mmm.components.saturation import SaturationTransformation


class BudgetOptimizer:
    """
    A class for optimizing budget allocation in a marketing mix model.

    Parameters:
    ----------
    adstock : AdstockTransformation
        The adstock class.
    saturation : SaturationTransformation
        The saturation class.
    num_days : int
        The number of days.
    parameters : dict
        A dictionary of parameters for each channel.
    adstock_first : bool, optional
        Whether to apply adstock transformation first or saturation transformation first.
        Default is True.
    """

    def __init__(
        self,
        adstock: AdstockTransformation,
        saturation: SaturationTransformation,
        num_days: int,
        parameters: dict[str, dict[str, dict[str, float]]],
        adstock_first: bool = True,
    ):
        self.adstock = adstock
        self.saturation = saturation
        self.num_days = num_days
        self.parameters = parameters
        self.adstock_first = adstock_first

    def objective(self, budgets: list[float]) -> float:
        """
        Calculate the total response during a period of time given the budgets,
        considering the saturation and adstock transformations.

        Parameters:
        ----------
        budgets : array_like
            The budgets for each channel.

        Returns:
        -------
        float
            The negative total response value.
        """
        total_response = 0
        first_transform, second_transform = (
            (self.adstock, self.saturation)
            if self.adstock_first
            else (self.saturation, self.adstock)
        )
        for idx, (_channel, params) in enumerate(self.parameters.items()):
            budget = budgets[idx]
            first_params = (
                params["adstock_params"]
                if self.adstock_first
                else params["saturation_params"]
            )
            second_params = (
                params["saturation_params"]
                if self.adstock_first
                else params["adstock_params"]
            )
            spend = np.full(self.num_days, budget)
            spend_extended = np.concatenate([spend, np.zeros(self.adstock.l_max)])
            transformed_spend = second_transform.function(
                x=first_transform.function(x=spend_extended, **first_params).eval(),
                **second_params,
            ).eval()
            total_response += np.sum(transformed_spend)
        return -total_response

    def allocate_budget(
        self,
        total_budget: float,
        budget_bounds: dict[str, tuple[float, float]] | None = None,
        custom_constraints: dict[Any, Any] | None = None,
    ):
        """
        Allocate the budget based on the total budget, budget bounds, and custom constraints.

        The default budget bounds are (0, total_budget) for each channel.

        The default constraint is the sum of all budgets should be equal to the total budget.

        The optimization is done using the Sequential Least Squares Quadratic Programming (SLSQP) method
        and it's constrained such that:
        1. The sum of budgets across all channels equals the total available budget.
        2. The budget allocated to each individual channel lies within its specified range.

        The purpuse is to maximize the total expected objective based on the inequality
        and equality constraints.

        Parameters:
        ----------
        total_budget : float
            The total budget.
        budget_bounds : dict, optional
            The budget bounds for each channel. Default is None.
        custom_constraints : dict, optional
            Custom constraints for the optimization. Default is None.

        Returns:
        -------
        dict
            The optimal budgets for each channel.
        float
            The negative total response value.
        """
        if budget_bounds is None:
            budget_bounds = {channel: (0, total_budget) for channel in self.parameters}
            warnings.warn(
                "No budget bounds provided. Using default bounds (0, total_budget) for each channel.",
                stacklevel=2,
            )
        else:
            if not isinstance(budget_bounds, dict):
                raise TypeError("`budget_bounds` should be a dictionary.")

        if custom_constraints is None:
            constraints = {"type": "eq", "fun": lambda x: np.sum(x) - total_budget}
            warnings.warn(
                "Using default equaliy constraint: The sum of all budgets should be equal to the total budget.",
                stacklevel=2,
            )
        else:
            if not isinstance(custom_constraints, dict):
                raise TypeError("`custom_constraints` should be a dictionary.")
            else:
                constraints = custom_constraints

        num_channels = len(self.parameters.keys())
        initial_guess = [
            total_budget // num_channels
        ] * num_channels  # np.linspace(1, 5, num_channels)
        bounds = [
            (
                (budget_bounds[channel][0], budget_bounds[channel][1])
                if channel in budget_bounds
                else (0, total_budget)
            )
            for channel in self.parameters
        ]
        result = minimize(
            self.objective,
            x0=initial_guess,
            bounds=bounds,
            constraints=constraints,
            method="SLSQP",
            options={"ftol": 1e-9, "maxiter": 1000},
        )
        if result.success:
            optimal_budgets = {
                name: budget
                for name, budget in zip(self.parameters.keys(), result.x, strict=False)
            }
            return optimal_budgets, -result.fun
        else:
            raise Exception("Optimization failed: " + result.message)
