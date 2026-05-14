# api/pagination.py
"""
Paginación personalizada para la API.
"""

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class StandardResultsSetPagination(PageNumberPagination):
    """Paginación estándar con tamaño configurable."""
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class EncomiendaPagination(PageNumberPagination):
    """Paginación específica para encomiendas."""
    page_size = 15
    page_size_query_param = 'page_size'
    max_page_size = 50
    
    def get_paginated_response(self, data):
        return Response({
            'links': {
                'next': self.get_next_link(),
                'previous': self.get_previous_link()
            },
            'count': self.page.paginator.count,
            'pages': self.page.paginator.num_pages,
            'current_page': self.page.number,
            'results': data
        })