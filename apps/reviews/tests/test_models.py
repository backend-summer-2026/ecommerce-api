from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import TestCase

from apps.orders.models import Order, OrderItem
from apps.products.models import Brand, Category, Product, ProductCategory, ProductVariant
from apps.reviews.models import (
    ProductRatingSummary,
    Review,
    ReviewImage,
    ReviewReply,
    ReviewStatus,
    ReviewVote,
    VoteType,
)

User = get_user_model()


class ReviewModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='reviewer@example.com',
            password='Password123!',
            first_name='Reviewer',
            last_name='User',
        )
        self.other_user = User.objects.create_user(
            email='other@example.com',
            password='Password123!',
            first_name='Other',
            last_name='User',
        )
        self.staff_user = User.objects.create_user(
            email='staff@example.com',
            password='Password123!',
            first_name='Staff',
            last_name='Admin',
            is_staff=True,
        )

        self.brand = Brand.objects.create(name='Apple', slug='apple')
        self.category = Category.objects.create(name='Smartphones', slug='smartphones')
        self.product = Product.objects.create(
            name='iPhone 15 Pro',
            slug='iphone-15-pro',
            brand=self.brand,
            description='Flagship smartphone',
        )
        ProductCategory.objects.create(
            product=self.product,
            category=self.category,
            is_primary=True,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            sku='IPHONE15P-128',
            price=Decimal('12000000.00'),
            is_default=True,
        )

        self.order = Order.objects.create(
            user=self.user,
            subtotal=Decimal('12000000.00'),
            total_price=Decimal('12000000.00'),
        )
        self.order_item = OrderItem.objects.create(
            order=self.order,
            variant=self.variant,
            product_name=self.product.name,
            variant_sku=self.variant.sku,
            unit_price=self.variant.price,
            quantity=1,
            total_price=self.variant.price,
        )

    def test_review_creation_and_defaults(self):
        review = Review.objects.create(
            user=self.user,
            product=self.product,
            rating=5,
            title='Amazing Phone!',
            comment='Super fast and battery lasts all day.',
            pros='Display, Camera, Battery',
            cons='Price',
        )

        self.assertEqual(review.status, ReviewStatus.PENDING)
        self.assertFalse(review.is_verified_purchase)
        self.assertEqual(review.likes_count, 0)
        self.assertEqual(review.dislikes_count, 0)
        self.assertEqual(review.rejection_reason, '')
        self.assertIn('5★', str(review))
        self.assertIn(self.product.name, str(review))

    def test_review_validation_rating_range(self):
        # Rating 0 should fail validation
        review_zero = Review(
            user=self.user,
            product=self.product,
            rating=0,
            comment='Too low rating',
        )
        with self.assertRaises(ValidationError):
            review_zero.clean()

        # Rating 6 should fail validation
        review_six = Review(
            user=self.user,
            product=self.product,
            rating=6,
            comment='Too high rating',
        )
        with self.assertRaises(ValidationError):
            review_six.clean()

        # Rating between 1 and 5 should pass
        review_valid = Review(
            user=self.user,
            product=self.product,
            rating=4,
            comment='Good product',
        )
        review_valid.clean()

    def test_review_unique_together_user_product(self):
        Review.objects.create(
            user=self.user,
            product=self.product,
            rating=5,
            comment='First review',
        )

        with self.assertRaises(IntegrityError):
            Review.objects.create(
                user=self.user,
                product=self.product,
                rating=3,
                comment='Duplicate review should fail',
            )

    def test_review_verified_purchase_with_order_item(self):
        review = Review.objects.create(
            user=self.user,
            product=self.product,
            order_item=self.order_item,
            rating=5,
            comment='Verified purchase review',
            is_verified_purchase=True,
        )
        self.assertTrue(review.is_verified_purchase)
        self.assertEqual(review.order_item, self.order_item)

    def test_review_moderation_approval_and_rejection(self):
        review = Review.objects.create(
            user=self.user,
            product=self.product,
            rating=5,
            comment='Pending moderation review',
        )
        self.assertEqual(review.status, ReviewStatus.PENDING)

        # Test approval
        review.approve()
        self.assertEqual(review.status, ReviewStatus.APPROVED)
        self.assertEqual(review.rejection_reason, '')

        summary = ProductRatingSummary.objects.get(product=self.product)
        self.assertEqual(summary.total_reviews, 1)
        self.assertEqual(summary.average_rating, Decimal('5.00'))

        # Test rejection
        review.reject(reason='Inappropriate language')
        self.assertEqual(review.status, ReviewStatus.REJECTED)
        self.assertEqual(review.rejection_reason, 'Inappropriate language')

        summary.refresh_from_db()
        self.assertEqual(summary.total_reviews, 0)
        self.assertEqual(summary.average_rating, Decimal('0.00'))

    def test_review_image_creation(self):
        review = Review.objects.create(
            user=self.user,
            product=self.product,
            rating=5,
            comment='Phone with photo',
        )
        dummy_image = SimpleUploadedFile(
            'photo.jpg',
            b'dummy_image_data',
            content_type='image/jpeg',
        )
        image = ReviewImage.objects.create(
            review=review,
            image=dummy_image,
            caption='Unboxing iPhone 15 Pro',
        )
        self.assertEqual(image.review, review)
        self.assertEqual(image.caption, 'Unboxing iPhone 15 Pro')
        self.assertIn(str(review.id), str(image))

    def test_review_reply_by_seller(self):
        review = Review.objects.create(
            user=self.user,
            product=self.product,
            rating=5,
            comment='Great phone!',
        )
        reply = ReviewReply.objects.create(
            review=review,
            user=self.staff_user,
            comment='Thank you for your valuable feedback!',
        )
        self.assertEqual(review.reply, reply)
        self.assertEqual(reply.user, self.staff_user)
        self.assertIn(str(review.id), str(reply))

        # Enforce OneToOne: attempting second reply on same review raises IntegrityError
        with self.assertRaises(IntegrityError):
            ReviewReply.objects.create(
                review=review,
                user=self.staff_user,
                comment='Second reply should not be allowed',
            )

    def test_review_vote_functionality_and_counters(self):
        review = Review.objects.create(
            user=self.user,
            product=self.product,
            rating=5,
            comment='Helpful detailed review',
        )

        # Other user votes HELPFUL
        vote = ReviewVote.objects.create(
            review=review,
            user=self.other_user,
            vote_type=VoteType.HELPFUL,
        )
        review.refresh_from_db()
        self.assertEqual(review.likes_count, 1)
        self.assertEqual(review.dislikes_count, 0)
        self.assertIn('HELPFUL', str(vote))

        # Other user changes vote to UNHELPFUL
        vote.vote_type = VoteType.UNHELPFUL
        vote.save()
        review.refresh_from_db()
        self.assertEqual(review.likes_count, 0)
        self.assertEqual(review.dislikes_count, 1)

        # Deleting vote updates counter
        vote.delete()
        review.refresh_from_db()
        self.assertEqual(review.likes_count, 0)
        self.assertEqual(review.dislikes_count, 0)

        # Unique together per user and review
        ReviewVote.objects.create(
            review=review,
            user=self.other_user,
            vote_type=VoteType.HELPFUL,
        )
        with self.assertRaises(IntegrityError):
            ReviewVote.objects.create(
                review=review,
                user=self.other_user,
                vote_type=VoteType.UNHELPFUL,
            )

    def test_product_rating_summary_recalculation(self):
        user2 = User.objects.create_user(email='u2@example.com', password='Password123!')
        user3 = User.objects.create_user(email='u3@example.com', password='Password123!')

        r1 = Review.objects.create(
            user=self.user,
            product=self.product,
            rating=5,
            comment='5 star review',
            status=ReviewStatus.APPROVED,
        )
        r2 = Review.objects.create(
            user=user2,
            product=self.product,
            rating=4,
            comment='4 star review',
            status=ReviewStatus.APPROVED,
        )
        r3 = Review.objects.create(
            user=user3,
            product=self.product,
            rating=1,
            comment='Pending review, should not count yet',
            status=ReviewStatus.PENDING,
        )

        summary = ProductRatingSummary.objects.get(product=self.product)
        # Only r1 and r2 are approved: (5 + 4) / 2 = 4.50
        self.assertEqual(summary.total_reviews, 2)
        self.assertEqual(summary.average_rating, Decimal('4.50'))
        self.assertEqual(summary.rating_5_count, 1)
        self.assertEqual(summary.rating_4_count, 1)
        self.assertEqual(summary.rating_1_count, 0)
        self.assertIn('4.5', str(summary))

        # Now approve r3: (5 + 4 + 1) / 3 = 3.33
        r3.approve()
        summary.refresh_from_db()
        self.assertEqual(summary.total_reviews, 3)
        self.assertEqual(summary.average_rating, Decimal('3.33'))
        self.assertEqual(summary.rating_1_count, 1)

        # Delete r3: summary should be recalculated
        r3.delete()
        summary.refresh_from_db()
        self.assertEqual(summary.total_reviews, 2)
        self.assertEqual(summary.average_rating, Decimal('4.50'))
        self.assertEqual(summary.rating_1_count, 0)
