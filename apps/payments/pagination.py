import math
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class BasePaymentPagination(PageNumberPagination):
    """
    Base pagination for payment records with structured metadata.
    """

    page_size_query_param = 'page_size'

    def get_paginated_response(self, data):
        total_items = self.page.paginator.count
        page_size = self.get_page_size(self.request) or self.page_size
        total_pages = math.ceil(total_items / page_size) if page_size else 1

        return Response({
            'count': total_items,
            'total_pages': total_pages,
            'current_page': self.page.number,
            'page_size': page_size,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data,
        })


class PaymentPagination(BasePaymentPagination):
    """Pagination for customer and admin payment listings."""
    page_size = 15
    max_page_size = 100


class RefundPagination(BasePaymentPagination):
    """Pagination for admin refund listings."""
    page_size = 15
    max_page_size = 100


class TransactionPagination(BasePaymentPagination):
    """Pagination for financial audit transactions."""
    page_size = 20
    max_page_size = 200
