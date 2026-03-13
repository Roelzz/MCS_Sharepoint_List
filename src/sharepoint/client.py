from typing import List, Dict, Any, Optional
from azure.identity import ClientSecretCredential
from msgraph import GraphServiceClient
from msgraph.generated.sites.item.lists.item.items.items_request_builder import ItemsRequestBuilder
from msgraph.generated.models.list_item_collection_response import ListItemCollectionResponse
from kiota_abstractions.base_request_configuration import RequestConfiguration
from kiota_abstractions.request_information import RequestInformation
from kiota_abstractions.method import Method

from ..config import settings

class SharePointClient:
    def __init__(self):
        self._credential = None
        self._client = None

    @property
    def credential(self):
        if self._credential is None:
            self._credential = ClientSecretCredential(
                tenant_id=settings.TENANT_ID,
                client_id=settings.CLIENT_ID,
                client_secret=settings.CLIENT_SECRET,
            )
        return self._credential

    @property
    def client(self):
        if self._client is None:
            self._client = GraphServiceClient(
                self.credential, scopes=["https://graph.microsoft.com/.default"]
            )
        return self._client

    async def get_site_lists(self, site_id: str) -> List[Dict[str, Any]]:
        """Get all lists in a site."""
        # This is a simplified wrapper. In a real implementation, we'd use the generated models.
        # But for quick prototyping, raw request execution or using the SDK models is fine.
        # Using SDK models is preferred but verbose.
        
        # Getting lists
        lists = await self.client.sites.by_site_id(site_id).lists.get()
        return lists.value if lists and lists.value else []

    async def get_list_columns(self, site_id: str, list_id: str) -> List[Dict[str, Any]]:
        """Get columns for a specific list."""
        columns = await self.client.sites.by_site_id(site_id).lists.by_list_id(list_id).columns.get()
        return columns.value if columns and columns.value else []

    async def get_list_item_count(self, site_id: str, list_id: str) -> int:
        """Get the number of items in a list (estimate from first page if $count unavailable)."""
        request_config = ItemsRequestBuilder.ItemsRequestBuilderGetRequestConfiguration(
            query_parameters=ItemsRequestBuilder.ItemsRequestBuilderGetQueryParameters(
                top=200,
            )
        )
        result = await self.client.sites.by_site_id(site_id).lists.by_list_id(list_id).items.get(request_configuration=request_config)
        if result and result.odata_count is not None:
            return result.odata_count
        count = len(result.value) if result and result.value else 0
        if result and result.odata_next_link:
            count = max(count, 200)
        return count

    async def get_list_items(self, site_id: str, list_id: str, top: int = 200, expand: str = "fields") -> List[Dict[str, Any]]:
        """Get items from a list with pagination."""
        request_config = ItemsRequestBuilder.ItemsRequestBuilderGetRequestConfiguration(
            query_parameters=ItemsRequestBuilder.ItemsRequestBuilderGetQueryParameters(
                top=top,
                expand=[expand]
            )
        )
        
        items = await self.client.sites.by_site_id(site_id).lists.by_list_id(list_id).items.get(request_configuration=request_config)
        
        all_items = []
        if items and items.value:
            all_items.extend(items.value)

            next_link = items.odata_next_link
            while next_link:
                if len(all_items) >= 5000:
                    break

                request_info = RequestInformation()
                request_info.http_method = Method.GET
                request_info.url = next_link
                next_page = await self.client.request_adapter.send_async(
                    request_info, ListItemCollectionResponse, {}
                )
                if next_page and next_page.value:
                    all_items.extend(next_page.value)
                    next_link = next_page.odata_next_link
                else:
                    break

        return all_items

    async def get_site_id_by_url(self, site_url: str) -> str:
        """Resolve site URL to site ID (hostname,sppath,guid)."""
        # Logic to parse URL and query graph
        # For now, assume site_id is passed directly or implement hostname lookup
        # standard format: hostname:/sites/sitename
        from urllib.parse import urlparse
        parsed = urlparse(site_url)
        hostname = parsed.hostname
        path = parsed.path.strip("/")
        
        site = await self.client.sites.by_site_id(f"{hostname}:/{path}").get()
        return site.id

# Singleton instance
sharepoint_client = SharePointClient()
