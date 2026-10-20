from rest_framework import serializers
from apps.products.models import Attribute, AttributeValue


class AttributeValueSerializer(serializers.ModelSerializer):
    """
    Serializer for attribute values.
    """
    class Meta:
        model = AttributeValue
        fields = ['id', 'value', 'slug']


class AttributeSerializer(serializers.ModelSerializer):
    """
    Serializer for attributes and their available values.
    """
    values = AttributeValueSerializer(many=True, read_only=True)

    class Meta:
        model = Attribute
        fields = ['id', 'name', 'slug', 'values']


class VariantAttributeValueOutputSerializer(serializers.Serializer):
    """
    Clean output representation of an attribute assigned to a product variant.
    """
    attribute_name = serializers.CharField(source='attribute_value.attribute.name')
    attribute_slug = serializers.CharField(source='attribute_value.attribute.slug')
    value = serializers.CharField(source='attribute_value.value')
    value_slug = serializers.CharField(source='attribute_value.slug')
