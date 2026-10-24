from rest_framework import serializers
from apps.dashboard.models import StockMovementLog
from apps.products.models import Inventory


class DashboardInventoryListSerializer(serializers.ModelSerializer):
    """
    Detailed stock inventory item representation for the backoffice list view.
    """
    variant_id = serializers.IntegerField(source='variant.id', read_only=True)
    sku = serializers.CharField(source='variant.sku', read_only=True)
    product_id = serializers.IntegerField(source='variant.product.id', read_only=True)
    product_name = serializers.CharField(source='variant.product.name', read_only=True)
    price = serializers.DecimalField(source='variant.price', max_digits=12, decimal_places=2, read_only=True)
    available_quantity = serializers.SerializerMethodField()
    is_low_stock = serializers.SerializerMethodField()
    is_out_of_stock = serializers.SerializerMethodField()

    class Meta:
        model = Inventory
        fields = [
            'id',
            'variant_id',
            'sku',
            'product_id',
            'product_name',
            'price',
            'quantity',
            'reserved_quantity',
            'available_quantity',
            'low_stock_threshold',
            'is_low_stock',
            'is_out_of_stock',
            'updated_at',
        ]

    def get_available_quantity(self, obj) -> int:
        return max(0, obj.quantity - obj.reserved_quantity)

    def get_is_low_stock(self, obj) -> bool:
        return 0 < obj.quantity <= obj.low_stock_threshold

    def get_is_out_of_stock(self, obj) -> bool:
        return obj.quantity <= 0


class StockAdjustmentSerializer(serializers.Serializer):
    """
    Payload for manual inventory adjustment by warehouse operator.
    """
    quantity_delta = serializers.IntegerField(
        required=True,
        help_text="Stock quantity delta to add (+) or deduct (-)",
    )
    reason = serializers.CharField(
        required=True,
        max_length=255,
        help_text="Operational explanation for this adjustment",
    )
    movement_type = serializers.ChoiceField(
        choices=StockMovementLog.StockMovementType.choices,
        default=StockMovementLog.StockMovementType.ADJUSTMENT,
    )

    def validate_quantity_delta(self, value):
        if value == 0:
            raise serializers.ValidationError("Miqdor o'zgarishi (quantity_delta) 0 bo'lishi mumkin emas.")
        return value


class StockMovementLogSerializer(serializers.ModelSerializer):
    """
    Audit log record representation for inventory movements.
    """
    variant_sku = serializers.CharField(source='variant.sku', read_only=True)
    product_name = serializers.CharField(source='variant.product.name', read_only=True)
    actor_email = serializers.SerializerMethodField()
    movement_type_display = serializers.CharField(source='get_movement_type_display', read_only=True)
    reference_order_number = serializers.CharField(
        source='reference_order.order_number',
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = StockMovementLog
        fields = [
            'id',
            'variant_id',
            'variant_sku',
            'product_name',
            'actor_email',
            'movement_type',
            'movement_type_display',
            'quantity_delta',
            'previous_quantity',
            'new_quantity',
            'reference_order_number',
            'reason',
            'created_at',
        ]

    def get_actor_email(self, obj) -> str:
        return obj.actor.email if obj.actor else 'Tizim'


class InventoryStatisticsSerializer(serializers.Serializer):
    """
    Aggregated inventory statistics.
    """
    total_skus = serializers.IntegerField()
    healthy_stock_count = serializers.IntegerField()
    low_stock_count = serializers.IntegerField()
    out_of_stock_count = serializers.IntegerField()
    total_units_in_stock = serializers.IntegerField()
    total_reserved_units = serializers.IntegerField()
