from typing import Dict, List, Optional, Union

import pymc as pm

from pymc_marketing.mmm.transformers import geometric_adstock, weibull_adstock
from pymc_marketing.mmm.utils import _get_distribution


class BaseFunction:
    REQUIRED_KEYS: List[str] = []

    def __init__(
        self,
        max_lagging: int = 4,
        model: Optional[pm.Model] = None,
        model_config: Optional[Dict] = None,
    ):
        self.max_lagging = max_lagging
        self.model = model
        self.model_config = self.initialize_model_config(model_config)

    def initialize_model_config(self, model_config: Optional[Dict]) -> Dict:
        if model_config is not None and not all(
            key in model_config for key in self.REQUIRED_KEYS
        ):
            update_model_config = {**model_config, **self._default_lagging_config}
        elif model_config is None:
            update_model_config = self._default_lagging_config
        else:
            update_model_config = model_config

        return update_model_config

    @property
    def _default_lagging_config(self) -> Dict:
        raise NotImplementedError("Subclasses should implement this method.")

    def apply(self, data):
        raise NotImplementedError("Subclasses must implement this method.")


class GeometricAdstockComponent(BaseFunction):
    """
    Geometric Adstock Component.

    This component applies geometric adstock transformation to the input data.
    It calculates the adstock effect of past marketing efforts on the current response.

    Parameters:
    -----------
    max_lagging : int
        The maximum lagging period to consider for adstock effect.
    model : pymc.Model
        The PyMC model object.
    model_config : dict
        The configuration dictionary for the model.

    Attributes:
    -----------
    REQUIRED_KEYS : list
        The list of required keys in the model_config dictionary.

    Methods:
    --------
    apply(data: Union[pm.Data, pm.MutableData]) -> pm.Deterministic:
        Apply the geometric adstock transformation to the input data.

    """

    REQUIRED_KEYS = [
        "adstock_alpha",
    ]

    def __init__(
        self,
        max_lagging: int = 4,
        model: Optional[pm.Model] = None,
        model_config: Optional[Dict] = None,
    ):
        super().__init__(max_lagging, model, model_config)

    @property
    def _default_lagging_config(self) -> Dict[str, Dict]:
        return {
            "adstock_alpha": {
                "dist": "Beta",
                "kwargs": {"alpha": 1, "beta": 3},
            }
        }

    @property
    def variable_mapping(self) -> Dict[str, str]:
        """The mapping from saturation function parameters to variables in a model."""
        return {
            "alpha": "adstock_alpha",
        }

    def apply(self, data: Union[pm.Data, pm.MutableData]) -> pm.Deterministic:
        """
        Apply the geometric adstock transformation to the input data.

        Parameters:
        -----------
        data : Union[pm.Data, pm.MutableData]
            The input data to apply the adstock transformation.

        Returns:
        --------
        pm.Deterministic
            The transformed data with adstock effect.

        """
        self.adstock_alpha_dist = _get_distribution(
            dist=self.model_config["adstock_alpha"]
        )

        with pm.modelcontext(self.model):
            adstock_alpha = self.adstock_alpha_dist(
                name="adstock_alpha",
                dims="channel",
                **self.model_config["adstock_alpha"]["kwargs"],
            )

            return geometric_adstock(
                x=data,
                alpha=adstock_alpha,
                l_max=self.max_lagging,
                normalize=True,
                axis=0,
            )


class WeibullPDFAdstockComponent(BaseFunction):
    """
    A class representing a Weibull PDF adstock component in a marketing mix model.

    Parameters:
    -----------
    max_lagging : int
        The maximum lagging value for the adstock component.
    model : pymc.Model
        The PyMC model object.
    model_config : dict
        The configuration dictionary for the model.

    Attributes:
    -----------
    REQUIRED_KEYS : list
        The list of required keys in the model configuration.

    Methods:
    --------
    apply(data: Union[pm.Data, pm.MutableData]) -> pm.Deterministic:
        Apply the Weibull PDF adstock component to the given data.

    """

    REQUIRED_KEYS = ["adstock_lambda", "adstock_shape"]

    def __init__(
        self,
        max_lagging: int = 4,
        model: Optional[pm.Model] = None,
        model_config: Optional[Dict] = None,
    ):
        super().__init__(max_lagging, model, model_config)

    @property
    def _default_lagging_config(self) -> Dict[str, Dict]:
        return {
            "adstock_lambda": {
                "dist": "Beta",
                "kwargs": {"alpha": 1, "beta": 3},
            },
            "adstock_shape": {
                "dist": "Beta",
                "kwargs": {"alpha": 1, "beta": 3},
            },
        }

    @property
    def variable_mapping(self) -> Dict[str, str]:
        """The mapping from saturation function parameters to variables in a model."""
        return {
            "lam": "adstock_lambda",
            "k": "adstock_shape",
        }

    def apply(self, data: Union[pm.Data, pm.MutableData]) -> pm.Deterministic:
        """
        Apply the Weibull PDF adstock component to the given data.

        Parameters:
        -----------
        data : Union[pm.Data, pm.MutableData]
            The data to apply the adstock component to.

        Returns:
        --------
        pm.Deterministic
            The adstocked data as a PyMC Deterministic variable.

        """
        self.adstock_lambda_dist = _get_distribution(
            dist=self.model_config["adstock_lambda"]
        )

        self.adstock_shape_dist = _get_distribution(
            dist=self.model_config["adstock_shape"]
        )

        with pm.modelcontext(self.model):
            adstock_lambda = self.adstock_lambda_dist(
                name="adstock_lambda",
                dims="channel",
                **self.model_config["adstock_lambda"]["kwargs"],
            )

            adstock_shape = self.adstock_shape_dist(
                name="adstock_shape",
                dims="channel",
                **self.model_config["adstock_shape"]["kwargs"],
            )

            return weibull_adstock(
                x=data,
                lam=adstock_lambda,
                k=adstock_shape,
                type="PDF",
                l_max=self.max_lagging,
            )


class WeibullCDFAdstockComponent(BaseFunction):
    """
    A class representing a Weibull CDF adstock component in a marketing mix model.

    Parameters:
    -----------
    max_lagging : int
        The maximum lagging value for the adstock component.
    model : pymc.Model
        The PyMC model object.
    model_config : dict
        The configuration dictionary for the model.

    Attributes:
    -----------
    REQUIRED_KEYS : list
        The list of required keys in the model configuration.

    Methods:
    --------
    apply(data: Union[pm.Data, pm.MutableData]) -> pm.Deterministic:
        Apply the Weibull CDF adstock component to the given data.

    """

    REQUIRED_KEYS = ["adstock_lambda", "adstock_shape"]

    def __init__(
        self,
        max_lagging: int = 4,
        model: Optional[pm.Model] = None,
        model_config: Optional[Dict] = None,
    ):
        """
        Initialize the WeibullCDFAdstockComponent.

        Parameters:
        -----------
        max_lagging : int
            The maximum lagging value for the adstock component.
        model : pymc.Model
            The PyMC model object.
        model_config : dict
            The configuration dictionary for the model.

        """
        super().__init__(max_lagging, model, model_config)

    @property
    def _default_lagging_config(self) -> Dict[str, Dict]:
        return {
            "adstock_lambda": {
                "dist": "Beta",
                "kwargs": {"alpha": 1, "beta": 3},
            },
            "adstock_shape": {
                "dist": "Beta",
                "kwargs": {"alpha": 1, "beta": 3},
            },
        }

    @property
    def variable_mapping(self) -> Dict[str, str]:
        """The mapping from saturation function parameters to variables in a model."""
        return {
            "lam": "adstock_lambda",
            "k": "adstock_shape",
        }

    def apply(self, data: Union[pm.Data, pm.MutableData]) -> pm.Deterministic:
        """
        Apply the Weibull CDF adstock component to the given data.

        Parameters:
        -----------
        data : Union[pm.Data, pm.MutableData]
            The data to apply the adstock component to.

        Returns:
        --------
        pm.Deterministic
            The adstocked data as a PyMC Deterministic variable.

        """
        self.adstock_lambda_dist = _get_distribution(
            dist=self.model_config["adstock_lambda"]
        )

        self.adstock_shape_dist = _get_distribution(
            dist=self.model_config["adstock_shape"]
        )

        with pm.modelcontext(self.model):
            adstock_lambda = self.adstock_lambda_dist(
                name="adstock_lambda",
                dims="channel",
                **self.model_config["adstock_lambda"]["kwargs"],
            )

            adstock_shape = self.adstock_shape_dist(
                name="adstock_shape",
                dims="channel",
                **self.model_config["adstock_shape"]["kwargs"],
            )

            return weibull_adstock(
                x=data,
                lam=adstock_lambda,
                k=adstock_shape,
                type="CDF",
                l_max=self.max_lagging,
            )


def _get_lagging_function(
    name: str,
    max_lagging: int = 4,
    model: Optional[pm.Model] = None,
    model_config: Optional[Dict] = None,
):
    """
    Get the lagging function based on the given name.

    Parameters:
    -----------
    name : str
        The name of the lagging function.
    max_lagging : int
        The maximum lagging value for the adstock component.
    model : pm.Model
        The PyMC model object.
    model_config : Optional[Dict], optional
        The configuration dictionary for the model, by default None.

    Returns:
    --------
    BaseFunction
        The lagging function object.

    Raises:
    -------
    ValueError
        If the lagging function name is not recognized.

    """
    lagging_functions = {
        "geometric": GeometricAdstockComponent,
        "weibull_pdf": WeibullPDFAdstockComponent,
        "weibull_cdf": WeibullCDFAdstockComponent,
        # Add other lagging function classes here as needed
    }

    if name in lagging_functions:
        return lagging_functions[name](
            max_lagging=max_lagging, model=model, model_config=model_config
        )
    else:
        raise ValueError(f"Lagging function {name} not recognized.")
