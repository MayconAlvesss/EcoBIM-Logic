<<<<<<< HEAD
import aiohttp
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class CarbonDatabaseConnector(ABC):
    @abstractmethod
    async def fetch_material_gwp(self, material_name):
        pass

class EC3Connector(CarbonDatabaseConnector):
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = 'https://buildingtransparency.org/api/materials'
        self.headers = {"Authorization": f"Bearer {self.api_key}"}

    async def fetch_material_gwp(self, q):
        logger.info(f"Fetching EPDs from EC3. Query: {q}")
        
        # FIXME: Uncomment the real code once the EC3 dev account is approved.
        # Returning a mock for now so we can test the UI.
        
        '''
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.base_url}?name={q}", headers=self.headers) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"EC3 Error: {response.status}")
                    return {}
        '''
        
        return {
            'source': "EC3_API_MOCK",
            "material": q,
            'declared_unit': "1 m3",
            "gwp_kgco2e": 350.5,
            'manufacturer': 'N/A'
=======
import aiohttp
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class CarbonDatabaseConnector(ABC):
    @abstractmethod
    async def fetch_material_gwp(self, material_name):
        pass

class EC3Connector(CarbonDatabaseConnector):
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = 'https://buildingtransparency.org/api/materials'
        self.headers = {"Authorization": f"Bearer {self.api_key}"}

    async def fetch_material_gwp(self, q):
        logger.info(f"Fetching EPDs from EC3. Query: {q}")
        
        # FIXME: Uncomment the real code once the EC3 dev account is approved.
        # Returning a mock for now so we can test the UI.
        
        '''
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.base_url}?name={q}", headers=self.headers) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"EC3 Error: {response.status}")
                    return {}
        '''
        
        return {
            'source': "EC3_API_MOCK",
            "material": q,
            'declared_unit': "1 m3",
            "gwp_kgco2e": 350.5,
            'manufacturer': 'N/A'
>>>>>>> e8bcca7 (Initial commit: EcoBIM 2025 functional)
        }