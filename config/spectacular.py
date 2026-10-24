"""
Spectacular OpenAPI Postprocessing and Customization Hooks.
"""

# Map URL path segments / module prefixes to canonical OpenAPI tags
PATH_TAG_MAPPING = {
    '/api/v1/auth/': 'Auth',
    '/api/v1/catalog/': 'Catalog',
    '/api/v1/cart/': 'Cart',
    '/api/v1/orders/': 'Orders',
    '/api/v1/payments/': 'Payments',
    '/api/v1/notifications/': 'Notifications',
    '/api/v1/reviews/': 'Reviews',
    '/api/v1/dashboard/': 'Dashboard',
}

NAME_TAG_MAPPING = {
    'auth': 'Auth',
    'catalog': 'Catalog',
    'cart': 'Cart',
    'orders': 'Orders',
    'payments': 'Payments',
    'notifications': 'Notifications',
    'reviews': 'Reviews',
    'dashboard': 'Dashboard',
}


def custom_tag_postprocessing_hook(result, generator, request, public):
    """
    Spectacular postprocessing hook to classify all endpoints into
    clean, human-readable tags and strip the generic 'v1' tag.
    """
    paths = result.get('paths', {})

    for path, path_item in paths.items():
        # Determine the canonical tag based on the URL path prefix
        canonical_tag = None
        for path_prefix, tag in PATH_TAG_MAPPING.items():
            if path.startswith(path_prefix):
                canonical_tag = tag
                break

        for method, operation in path_item.items():
            if not isinstance(operation, dict):
                continue

            current_tags = operation.get('tags', [])

            # Filter out generic 'v1' tag
            filtered_tags = [t for t in current_tags if t.lower() != 'v1']

            # Map existing lower-case or custom tags to canonical tags
            mapped_tags = []
            for t in filtered_tags:
                mapped_tags.append(NAME_TAG_MAPPING.get(t.lower(), t))

            # If no valid tag remains or canonical tag determined, assign canonical tag
            if canonical_tag and canonical_tag not in mapped_tags:
                mapped_tags.insert(0, canonical_tag)

            # Assign back the updated tags
            operation['tags'] = mapped_tags or [canonical_tag or 'General']

    return result
