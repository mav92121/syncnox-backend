from app.crud.base import CRUDBase
from app.crud.team_member import team_member
from .depot import depot
from .vehicle import vehicle
from .job import job

__all__ = ["CRUDBase", "team_member", "depot", "vehicle", "job"]
