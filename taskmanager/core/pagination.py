"""Paging for every list endpoint."""

from django.conf import settings
from rest_framework.pagination import PageNumberPagination


class DefaultPagination(PageNumberPagination):
    """?page=&page_size= with the default and maximum from settings (read per request)."""

    page_size_query_param = "page_size"

    def __init__(self):
        self.page_size = settings.TASKMANAGER_PAGE_SIZE
        self.max_page_size = settings.TASKMANAGER_MAX_PAGE_SIZE
