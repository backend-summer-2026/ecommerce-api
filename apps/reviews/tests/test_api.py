from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

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


class ReviewAPITests(APITestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            email='customer@example.com',
            password='Password123!',
            first_name='Ali',
            last_name='Valiyev',
        )
        self.stranger = User.objects.create_user(
            email='stranger@example.com',
            password='Password123!',
            first_name='Stranger',
            last_name='User',
        )
        self.admin = User.objects.create_user(
            email='admin@example.com',
            password='Password123!',
            first_name='Admin',
            last_name='Staff',
            is_staff=True,
        )

        self.brand = Brand.objects.create(name='Samsung', slug='samsung')
        self.category = Category.objects.create(name='Electronics', slug='electronics')
        self.product = Product.objects.create(
            name='Galaxy S24 Ultra',
            slug='galaxy-s24-ultra',
            brand=self.brand,
            description='Flagship AI phone',
        )
        ProductCategory.objects.create(
            product=self.product,
            category=self.category,
            is_primary=True,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            sku='S24U-256',
            price=Decimal('15000000.00'),
            is_default=True,
        )

        self.order = Order.objects.create(
            user=self.customer,
            subtotal=Decimal('15000000.00'),
            total_price=Decimal('15000000.00'),
            status=Order.OrderStatus.DELIVERED,
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

    def test_product_rating_summary_endpoint(self):
        url = reverse('reviews:product-rating-summary', kwargs={'product_id': self.product.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['product'], self.product.id)
        self.assertEqual(Decimal(str(response.data['average_rating'])), Decimal('0.00'))
        self.assertEqual(response.data['total_reviews'], 0)

    def test_product_review_submission_verified_purchase(self):
        url = reverse('reviews:product-reviews-list-create', kwargs={'product_id': self.product.id})

        payload = {
            'rating': 5,
            'title': 'Best phone ever!',
            'comment': 'Amazing display, battery, and AI camera features.',
            'pros': 'Camera, Screen, Pen',
            'cons': 'Pricey',
        }
        resp_unauth = self.client.post(url, payload)
        self.assertEqual(resp_unauth.status_code, status.HTTP_401_UNAUTHORIZED)

        self.client.force_authenticate(user=self.customer)
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['rating'], 5)
        self.assertEqual(response.data['status'], ReviewStatus.PENDING)
        self.assertTrue(response.data['is_verified_purchase'])

        resp_duplicate = self.client.post(url, payload)
        self.assertEqual(resp_duplicate.status_code, status.HTTP_400_BAD_REQUEST)

    def test_product_reviews_list_and_filters(self):
        r1 = Review.objects.create(
            product=self.product,
            user=self.customer,
            rating=5,
            comment='Super phone 5 stars',
            status=ReviewStatus.APPROVED,
            is_verified_purchase=True,
            likes_count=10,
        )
        r2 = Review.objects.create(
            product=self.product,
            user=self.stranger,
            rating=3,
            comment='Decent phone 3 stars',
            status=ReviewStatus.APPROVED,
            is_verified_purchase=False,
            likes_count=2,
        )
        user3 = User.objects.create_user(email='user3@example.com', password='Password123!')
        Review.objects.create(
            product=self.product,
            user=user3,
            rating=1,
            comment='Bad phone',
            status=ReviewStatus.PENDING,
        )

        url = reverse('reviews:product-reviews-list-create', kwargs={'product_id': self.product.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)

        resp_rating5 = self.client.get(f"{url}?rating=5")
        self.assertEqual(resp_rating5.data['count'], 1)
        self.assertEqual(resp_rating5.data['results'][0]['rating'], 5)

        resp_verified = self.client.get(f"{url}?verified_only=true")
        self.assertEqual(resp_verified.data['count'], 1)
        self.assertTrue(resp_verified.data['results'][0]['is_verified_purchase'])

        resp_sorted = self.client.get(f"{url}?ordering=-likes_count")
        self.assertEqual(resp_sorted.data['results'][0]['id'], r1.id)

    def test_review_detail_edit_and_delete_permissions(self):
        review = Review.objects.create(
            product=self.product,
            user=self.customer,
            rating=4,
            comment='Good phone initially',
            status=ReviewStatus.APPROVED,
        )

        url = reverse('reviews:review-detail', kwargs={'id': review.id})

        resp_get = self.client.get(url)
        self.assertEqual(resp_get.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_get.data['id'], review.id)

        self.client.force_authenticate(user=self.stranger)
        resp_stranger_edit = self.client.patch(url, {'comment': 'Hacked review'})
        self.assertEqual(resp_stranger_edit.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.customer)
        resp_owner_edit = self.client.patch(url, {'comment': 'Updated review after 1 month'})
        self.assertEqual(resp_owner_edit.status_code, status.HTTP_200_OK)
        review.refresh_from_db()
        self.assertEqual(review.comment, 'Updated review after 1 month')
        self.assertEqual(review.status, ReviewStatus.PENDING)

        self.client.force_authenticate(user=self.stranger)
        resp_stranger_del = self.client.delete(url)
        self.assertEqual(resp_stranger_del.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.customer)
        resp_owner_del = self.client.delete(url)
        self.assertEqual(resp_owner_del.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Review.objects.filter(id=review.id).exists())

    def test_review_image_upload_and_delete(self):
        review = Review.objects.create(
            product=self.product,
            user=self.customer,
            rating=5,
            comment='Review with photo',
            status=ReviewStatus.APPROVED,
        )

        upload_url = reverse('reviews:review-image-upload', kwargs={'id': review.id})

        dummy_image = SimpleUploadedFile('phone.jpg', b'image_bytes', content_type='image/jpeg')

        self.client.force_authenticate(user=self.stranger)
        resp_stranger = self.client.post(upload_url, {'image': dummy_image}, format='multipart')
        self.assertEqual(resp_stranger.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.customer)
        dummy_image.seek(0)
        resp_upload = self.client.post(
            upload_url,
            {'image': dummy_image, 'caption': 'Unboxed phone'},
            format='multipart',
        )
        self.assertEqual(resp_upload.status_code, status.HTTP_201_CREATED)
        image_id = resp_upload.data['id']
        self.assertEqual(resp_upload.data['caption'], 'Unboxed phone')

        delete_url = reverse('reviews:review-image-delete', kwargs={'image_id': image_id})
        self.client.force_authenticate(user=self.stranger)
        resp_del_stranger = self.client.delete(delete_url)
        self.assertEqual(resp_del_stranger.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.customer)
        resp_del_owner = self.client.delete(delete_url)
        self.assertEqual(resp_del_owner.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ReviewImage.objects.filter(id=image_id).exists())

    def test_review_helpful_vote_toggle(self):
        review = Review.objects.create(
            product=self.product,
            user=self.customer,
            rating=5,
            comment='Very informative review',
            status=ReviewStatus.APPROVED,
        )

        vote_url = reverse('reviews:review-vote', kwargs={'id': review.id})

        self.client.force_authenticate(user=self.stranger)
        resp1 = self.client.post(vote_url, {'vote_type': VoteType.HELPFUL})
        self.assertEqual(resp1.status_code, status.HTTP_200_OK)
        self.assertEqual(resp1.data['action'], 'created')
        self.assertEqual(resp1.data['likes_count'], 1)
        self.assertEqual(resp1.data['dislikes_count'], 0)

        resp2 = self.client.post(vote_url, {'vote_type': VoteType.HELPFUL})
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertEqual(resp2.data['action'], 'removed')
        self.assertEqual(resp2.data['likes_count'], 0)
        self.assertIsNone(resp2.data['vote_type'])

        resp3 = self.client.post(vote_url, {'vote_type': VoteType.UNHELPFUL})
        self.assertEqual(resp3.status_code, status.HTTP_200_OK)
        self.assertEqual(resp3.data['action'], 'created')
        self.assertEqual(resp3.data['dislikes_count'], 1)

    def test_seller_reply_endpoint(self):
        review = Review.objects.create(
            product=self.product,
            user=self.customer,
            rating=5,
            comment='Review waiting for seller response',
            status=ReviewStatus.APPROVED,
        )

        reply_url = reverse('reviews:review-reply', kwargs={'id': review.id})

        self.client.force_authenticate(user=self.customer)
        resp_cust = self.client.post(reply_url, {'comment': 'Unauthorized reply'})
        self.assertEqual(resp_cust.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.admin)
        resp_admin = self.client.post(
            reply_url,
            {'comment': 'Thank you Ali for your wonderful review!'},
        )
        self.assertEqual(resp_admin.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_admin.data['comment'], 'Thank you Ali for your wonderful review!')
        self.assertTrue(ReviewReply.objects.filter(review=review).exists())

    def test_admin_review_moderation(self):
        review = Review.objects.create(
            product=self.product,
            user=self.customer,
            rating=5,
            comment='Review for moderation test',
            status=ReviewStatus.PENDING,
        )

        mod_list_url = reverse('reviews:admin-review-moderation-list')
        moderate_url = reverse('reviews:admin-review-moderate', kwargs={'id': review.id})

        self.client.force_authenticate(user=self.customer)
        resp_unauth = self.client.get(mod_list_url)
        self.assertEqual(resp_unauth.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.admin)
        resp_list = self.client.get(mod_list_url)
        self.assertEqual(resp_list.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_list.data['count'], 1)

        resp_approve = self.client.post(moderate_url, {'status': ReviewStatus.APPROVED})
        self.assertEqual(resp_approve.status_code, status.HTTP_200_OK)
        review.refresh_from_db()
        self.assertEqual(review.status, ReviewStatus.APPROVED)

        summary = ProductRatingSummary.objects.get(product=self.product)
        self.assertEqual(summary.total_reviews, 1)
        self.assertEqual(summary.average_rating, Decimal('5.00'))

        resp_reject = self.client.post(
            moderate_url,
            {'status': ReviewStatus.REJECTED, 'rejection_reason': 'Violates review terms'},
        )
        self.assertEqual(resp_reject.status_code, status.HTTP_200_OK)
        review.refresh_from_db()
        self.assertEqual(review.status, ReviewStatus.REJECTED)
        self.assertEqual(review.rejection_reason, 'Violates review terms')
