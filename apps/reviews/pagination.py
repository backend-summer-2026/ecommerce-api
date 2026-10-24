from rest_framework.pagination import PageNumberPagination


class ReviewPagination(PageNumberPagination):
    """
    Pagination for customer reviews listings.
    Defaults to 10 reviews per page with client override up to 50.
    """
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 50
