from typing import Optional
from http_cpe_manager.models.base import CPE_HTTP_Controller
from cpe_manager.models import vsol

CONTROLLERS = {
    'vsol_v2802dac': vsol._2802dac.Controller
}

def get_controller(model_name: str) -> Optional[CPE_HTTP_Controller]:
    return CONTROLLERS.get(model_name)
