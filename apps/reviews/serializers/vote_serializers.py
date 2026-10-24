from rest_framework import serializers

from apps.reviews.models import ReviewVote, VoteType


class ReviewVoteSerializer(serializers.ModelSerializer):
    """
    Serializer for voting whether a review was helpful or unhelpful.
    """

    class Meta:
        model = ReviewVote
        fields = [
            'id',
            'review',
            'user',
            'vote_type',
            'created_at',
        ]
        read_only_fields = ['id', 'review', 'user', 'created_at']

    def validate_vote_type(self, value):
        if value not in VoteType.values:
            raise serializers.ValidationError(
                f"Invalid vote type. Must be one of: {', '.join(VoteType.values)}"
            )
        return value
