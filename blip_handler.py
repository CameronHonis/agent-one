import logging
from collections import deque

from models.blip import Blip

logger = logging.getLogger(__name__)


class BlipHandler:
    def __init__(self):
        self.mem = deque()

    def handle(self, blip: Blip):
        logger.info(str(blip))
        
