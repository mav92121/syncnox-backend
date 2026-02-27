from app.crud.base import CRUDBase
from app.crud.team_member import team_member
from .depot import depot
from .vehicle import vehicle
from .job import job
from .optimization_request import optimization_request
from .dashboard import dashboard

__all__ = ["CRUDBase", "team_member", "depot", "vehicle", "job", "optimization_request", "dashboard"]
