from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, db_index=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
    )
    icon = models.ImageField(upload_to='categories/icons/', null=True, blank=True)
    image = models.ImageField(upload_to='categories/images/', null=True, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'categories'
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
        ordering = ['name']

    def get_full_path(self) -> str:
        """
        Returns full hierarchy path like 'Electronics > Computers > Laptops'.
        """
        path = [self.name]
        current = self.parent
        while current is not None:
            path.append(current.name)
            current = current.parent
        return ' > '.join(reversed(path))

    def __str__(self) -> str:
        return self.get_full_path()


class Brand(models.Model):
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True, db_index=True)
    logo = models.ImageField(upload_to='brands/logos/', null=True, blank=True)
    description = models.TextField(blank=True)
    website = models.URLField(max_length=500, blank=True, null=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'brands'
        verbose_name = 'Brand'
        verbose_name_plural = 'Brands'
        ordering = ['name']

    def __str__(self) -> str:
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, db_index=True)
    brand = models.ForeignKey(
        Brand,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products',
    )
    categories = models.ManyToManyField(
        Category,
        through='ProductCategory',
        related_name='products',
    )
    description = models.TextField(blank=True)
    short_description = models.CharField(max_length=500, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'products'
        verbose_name = 'Product'
        verbose_name_plural = 'Products'
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['is_active', 'created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self) -> str:
        return self.name


class ProductCategory(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='product_categories',
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='product_categories',
    )
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'product_categories'
        verbose_name = 'Product Category'
        verbose_name_plural = 'Product Categories'
        unique_together = ('product', 'category')

    def __str__(self) -> str:
        category_type = 'Primary' if self.is_primary else 'Secondary'
        return f"{self.product.name} - {self.category.name} ({category_type})"


class ProductVariant(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='variants',
    )
    title = models.CharField(max_length=255, blank=True)
    sku = models.CharField(max_length=100, unique=True, db_index=True)
    price = models.DecimalField(max_digits=14, decimal_places=2)
    discount_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
    )
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True, db_index=True)
    attributes = models.ManyToManyField(
        'AttributeValue',
        through='ProductVariantAttributeValue',
        related_name='variants',
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'product_variants'
        verbose_name = 'Product Variant'
        verbose_name_plural = 'Product Variants'
        ordering = ['-is_default', 'id']

    def __str__(self) -> str:
        title_or_sku = self.title or self.sku
        return f"{self.product.name} - {title_or_sku}"

    @property
    def final_price(self) -> Decimal:
        if self.discount_price is not None and self.discount_price < self.price:
            return self.discount_price
        return self.price

    @property
    def is_on_sale(self) -> bool:
        return self.discount_price is not None and self.discount_price < self.price


class ProductMedia(models.Model):
    class MediaType(models.TextChoices):
        IMAGE = 'image', 'Image'
        VIDEO = 'video', 'Video'

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='media',
    )
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='media',
    )
    file = models.FileField(upload_to='products/%Y/%m/')
    alt_text = models.CharField(max_length=255, blank=True)
    media_type = models.CharField(
        max_length=20,
        choices=MediaType.choices,
        default=MediaType.IMAGE,
    )
    is_main = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'product_media'
        verbose_name = 'Product Media'
        verbose_name_plural = 'Product Media'
        ordering = ['order', '-is_main', 'id']

    def __str__(self) -> str:
        return f"Media for {self.product.name} ({self.media_type})"


class Attribute(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'attributes'
        verbose_name = 'Attribute'
        verbose_name_plural = 'Attributes'
        ordering = ['name']

    def __str__(self) -> str:
        return self.name


class AttributeValue(models.Model):
    attribute = models.ForeignKey(
        Attribute,
        on_delete=models.CASCADE,
        related_name='values',
    )
    value = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'attribute_values'
        verbose_name = 'Attribute Value'
        verbose_name_plural = 'Attribute Values'
        unique_together = ('attribute', 'value')
        ordering = ['attribute__name', 'value']

    def __str__(self) -> str:
        return f"{self.attribute.name}: {self.value}"


class ProductVariantAttributeValue(models.Model):
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.CASCADE,
        related_name='variant_attributes',
    )
    attribute_value = models.ForeignKey(
        AttributeValue,
        on_delete=models.CASCADE,
        related_name='variant_attributes',
    )

    class Meta:
        db_table = 'variant_attribute_values'
        verbose_name = 'Variant Attribute Value'
        verbose_name_plural = 'Variant Attribute Values'
        unique_together = ('variant', 'attribute_value')

    def __str__(self) -> str:
        return f"{self.variant} - {self.attribute_value}"


class Inventory(models.Model):
    variant = models.OneToOneField(
        ProductVariant,
        on_delete=models.CASCADE,
        related_name='inventory',
    )
    quantity = models.PositiveIntegerField(default=0)
    reserved_quantity = models.PositiveIntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(default=5)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'inventory'
        verbose_name = 'Inventory'
        verbose_name_plural = 'Inventories'

    def __str__(self) -> str:
        return f"Inventory for {self.variant.sku} (Available: {self.available_quantity})"

    @property
    def available_quantity(self) -> int:
        return max(0, self.quantity - self.reserved_quantity)

    @property
    def is_in_stock(self) -> bool:
        return self.available_quantity > 0

    @property
    def is_low_stock(self) -> bool:
        return 0 < self.available_quantity <= self.low_stock_threshold

    def reserve(self, amount: int):
        """
        Reserves stock quantity for active checkouts or orders.
        """
        if amount <= 0:
            raise ValidationError("Reservation amount must be greater than zero.")
        if self.available_quantity < amount:
            raise ValidationError(
                f"Insufficient stock to reserve {amount} items. Available: {self.available_quantity}"
            )
        self.reserved_quantity += amount
        self.save(update_fields=['reserved_quantity', 'updated_at'])

    def release(self, amount: int):
        """
        Releases reserved stock back to available stock.
        """
        if amount <= 0:
            raise ValidationError("Release amount must be greater than zero.")
        if self.reserved_quantity < amount:
            raise ValidationError(
                f"Cannot release {amount} items. Currently reserved: {self.reserved_quantity}"
            )
        self.reserved_quantity -= amount
        self.save(update_fields=['reserved_quantity', 'updated_at'])

    def deduct(self, amount: int):
        """
        Deducts physical stock when an order is fulfilled.
        Reduces both physical quantity and reserved quantity (if reserved).
        """
        if amount <= 0:
            raise ValidationError("Deduct amount must be greater than zero.")
        if self.quantity < amount:
            raise ValidationError(
                f"Cannot deduct {amount} items. Total on-hand quantity: {self.quantity}"
            )
        self.quantity -= amount
        if self.reserved_quantity >= amount:
            self.reserved_quantity -= amount
        else:
            self.reserved_quantity = 0
        self.save(update_fields=['quantity', 'reserved_quantity', 'updated_at'])
