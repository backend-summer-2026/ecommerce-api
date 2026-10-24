from rest_framework import serializers

from apps.reviews.models import ReviewReply


class ReviewReplySerializer(serializers.ModelSerializer):
    """
    Serializer for merchant/staff official responses to customer reviews.
    """

    user_name = serializers.SerializerMethodField()

    class Meta:
        model = ReviewReply
        fields = [
            'id',
            'review',
            'user',
            'user_name',
            'comment',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'review', 'user', 'created_at', 'updated_at']

    def get_user_name(self, obj) -> str:
        if obj.user:
            name = f"{obj.user.first_name} {obj.user.last_name}".strip()
            return name if name else obj.user.email
        return "Store Team"
