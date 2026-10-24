from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.reviews.models import ProductRatingSummary, Review, ReviewVote


@receiver(post_save, sender=Review)
def sync_rating_summary_on_save(sender, instance, **kwargs):
    """
    Synchronizes ProductRatingSummary when a review is created, approved,
    rejected, or has its rating modified.
    """
    summary, _ = ProductRatingSummary.objects.get_or_create(product=instance.product)
    summary.recalculate()


@receiver(post_delete, sender=Review)
def sync_rating_summary_on_delete(sender, instance, **kwargs):
    """
    Synchronizes ProductRatingSummary when a review is deleted.
    """
    try:
        summary = ProductRatingSummary.objects.get(product=instance.product)
        summary.recalculate()
    except ProductRatingSummary.DoesNotExist:
        pass


@receiver(post_save, sender=ReviewVote)
def sync_votes_on_save(sender, instance, **kwargs):
    """
    Ensures Review likes_count and dislikes_count are updated when a vote is added/updated.
    """
    instance.review.update_helpful_counts()


@receiver(post_delete, sender=ReviewVote)
def sync_votes_on_delete(sender, instance, **kwargs):
    """
    Ensures Review likes_count and dislikes_count are updated when a vote is deleted.
    """
    instance.review.update_helpful_counts()
