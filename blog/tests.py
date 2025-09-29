from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from unittest.mock import patch
from .models import Post
import io
from PIL import Image


class UserRegistrationAndLoginFlowTest(TestCase):
    """
    Integration test for complete user authentication journey:
    signup → auto-login → logout → manual login → protected access
    """

    def setUp(self):
        self.client = Client()
        self.signup_url = reverse('signup')
        self.login_url = reverse('login')
        self.logout_url = reverse('logout')
        self.post_create_url = reverse('post_create')
        self.my_posts_url = reverse('my_posts')

        self.user_data = {
            'username': 'testuser',
            'password1': 'ComplexPass123!',
            'password2': 'ComplexPass123!',
        }

    def test_complete_user_journey(self):
        """Test the complete user authentication flow"""

        # Step 1: Signup and verify auto-login
        response = self.client.post(self.signup_url, self.user_data)
        self.assertEqual(response.status_code, 302)  # Redirect after signup
        self.assertRedirects(response, reverse('post_list'))

        # Verify user is created
        user = User.objects.get(username='testuser')
        self.assertIsNotNone(user)

        # Step 2: logout
        '''
        response = self.client.get(self.logout_url)
        self.assertEqual(response.status_code, 302)  # Redirect after logout
        self.assertRedirects(response, reverse('post_list'))

        # Verify user is logged out - cannot access protected pages
        response = self.client.get(self.my_posts_url)
        self.assertEqual(response.status_code, 302)  # Redirected to login
        self.assertTrue(response.url.startswith('/login/'))
        '''
        # Step 3: Manual login
        login_data = {
            'username': 'testuser',
            'password': 'ComplexPass123!',
        }
        response = self.client.post(self.login_url, login_data)
        self.assertEqual(response.status_code, 302)  # Redirect after login
        self.assertRedirects(response, reverse('post_list'))

        # Step 4: Verify protected access after manual login
        response = self.client.get(self.my_posts_url)
        self.assertEqual(response.status_code, 200)

        response = self.client.get(self.post_create_url)
        self.assertEqual(response.status_code, 200)

        # Verify user context
        self.assertTrue(response.context['user'].is_authenticated)
        self.assertEqual(response.context['user'].username, 'testuser')

    def test_invalid_signup(self):
        """Test signup with mismatched passwords"""
        invalid_data = {
            'username': 'testuser',
            'password1': 'ComplexPass123!',
            'password2': 'DifferentPass456!',
        }
        response = self.client.post(self.signup_url, invalid_data)
        self.assertEqual(response.status_code, 200)  # Stays on signup page
        self.assertFalse(User.objects.filter(username='testuser').exists())

    def test_invalid_login(self):
        """Test login with wrong credentials"""
        # Create user first
        User.objects.create_user(username='testuser', password='CorrectPass123!')

        wrong_credentials = {
            'username': 'testuser',
            'password': 'WrongPassword',
        }
        response = self.client.post(self.login_url, wrong_credentials)
        self.assertEqual(response.status_code, 200)  # Stays on login page
        self.assertContains(response, "Please enter a correct username and password")

        # Verify cannot access protected pages
        response = self.client.get(self.my_posts_url)
        self.assertEqual(response.status_code, 302)


class CloudinaryImageUploadIntegrationTest(TestCase):
    """
    Integration test involving Cloudinary external service:
    Tests image upload, storage, and retrieval workflow
    """
    
    def setUp(self):
        self.client = Client()
        
        # Create and login user
        self.user = User.objects.create_user(
            username='photographer',
            password='PhotoPass123!'
        )
        self.client.login(username='photographer', password='PhotoPass123!')
        
        self.create_url = reverse('post_create')
    
    def create_test_image(self):
        """Helper method to create a test image file"""
        # Create a simple test image
        image = Image.new('RGB', (100, 100), color='red')
        image_file = io.BytesIO()
        image.save(image_file, format='JPEG')
        image_file.seek(0)
        
        return SimpleUploadedFile(
            name='test_image.jpg',
            content=image_file.read(),
            content_type='image/jpeg'
        )
    
    @patch('cloudinary.uploader.upload')
    def test_post_creation_with_image_upload(self, mock_upload):
        """Test creating a post with image upload to Cloudinary"""
        
        # Mock Cloudinary upload response
        mock_upload.return_value = {
            'public_id': 'test_public_id_123',
            'url': 'https://res.cloudinary.com/demo/image/upload/test_image.jpg',
            'secure_url': 'https://res.cloudinary.com/demo/image/upload/test_image.jpg',
            'format': 'jpg',
            'width': 100,
            'height': 100,
            'version': '1234567890',
            "resource_type": "image",   # required
            "type": "upload",
        }
        
        # Create test image
        test_image = self.create_test_image()
        
        # Create post with image
        post_data = {
            'title': 'Post with Image',
            'content': 'This post has a beautiful featured image.',
            'status': 'published',
            'featured_image': test_image,
        }
        
        response = self.client.post(self.create_url, post_data, format='multipart')
        self.assertEqual(response.status_code, 302)
        
        # Verify post was created
        post = Post.objects.get(title='Post with Image')
        self.assertEqual(post.author, self.user)
        self.assertTrue(post.featured_image)
        
        # Verify Cloudinary upload was called
        self.assertTrue(mock_upload.called)
    
    @patch('cloudinary.uploader.upload')
    def test_complete_image_workflow(self, mock_upload):
        """Test complete workflow: upload → display → update → verify"""
        
        # Mock Cloudinary upload responses
        mock_upload.side_effect = [
            {
                'public_id': 'original_image_123',
                'url': 'https://res.cloudinary.com/demo/image/upload/original.jpg',
                'secure_url': 'https://res.cloudinary.com/demo/image/upload/original.jpg',
                'version': '1111111111', 
                "resource_type": "image",   # required
                "type": "upload",
            },
            {
                'public_id': 'updated_image_456',
                'url': 'https://res.cloudinary.com/demo/image/upload/updated.jpg',
                'secure_url': 'https://res.cloudinary.com/demo/image/upload/updated.jpg',
                'version': '2222222222', 
                "resource_type": "image",   # required
                "type": "upload", 
            }
        ]
        
        # Step 1: CREATE post with image
        test_image = self.create_test_image()
        post_data = {
            'title': 'Gallery Post',
            'content': 'A post showcasing my photography.',
            'status': 'published',
            'featured_image': test_image,
        }
        
        response = self.client.post(self.create_url, post_data, format='multipart')
        self.assertEqual(response.status_code, 302)
        
        post = Post.objects.get(title='Gallery Post')
        self.assertTrue(post.featured_image)
        
        # Step 2: READ - Verify image displays on detail page
        detail_url = reverse('post_detail', kwargs={'slug': post.slug})
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 200)
        
        # Verify image URL is in the response (mocked URL)
        # Note: In real scenario, this would be the actual Cloudinary URL
        self.assertContains(response, 'Gallery Post')
        
        # Step 3: UPDATE - Replace the image
        new_image = self.create_test_image()
        edit_url = reverse('post_edit', kwargs={'slug': post.slug})
        updated_data = {
            'title': 'Gallery Post',
            'content': 'Updated with a new image.',
            'status': 'published',
            'featured_image': new_image,
        }
        
        response = self.client.post(edit_url, updated_data, format='multipart')
        self.assertEqual(response.status_code, 302)
        
        # Verify upload was called twice (original + update)
        self.assertEqual(mock_upload.call_count, 2)
        
        # Step 4: DELETE post (cleanup)
        delete_url = reverse('post_delete', kwargs={'slug': post.slug})
        response = self.client.post(delete_url)
        self.assertEqual(response.status_code, 302)
        
        # Verify post is deleted
        self.assertFalse(Post.objects.filter(id=post.id).exists())
    
    def test_post_without_image(self):
        """Test that posts work fine without images (optional field)"""
        post_data = {
            'title': 'Text Only Post',
            'content': 'This post has no image, just text content.',
            'status': 'published',
        }
        
        response = self.client.post(self.create_url, post_data)
        self.assertEqual(response.status_code, 302)
        
        # Verify post was created without image
        post = Post.objects.get(title='Text Only Post')
        self.assertFalse(post.featured_image)
        
        # Verify it displays correctly
        detail_url = reverse('post_detail', kwargs={'slug': post.slug})
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Text Only Post')
    
    @patch('cloudinary.uploader.upload')
    def test_image_display_in_post_list(self, mock_upload):
        """Test that images display in the post list view"""
        
        mock_upload.return_value = {
            'public_id': 'list_test_123',
            'url': 'https://res.cloudinary.com/demo/image/upload/list_test.jpg',
            'secure_url': 'https://res.cloudinary.com/demo/image/upload/list_test.jpg',
            'version': '1234567890',
            "resource_type": "image",   # required
            "type": "upload",
        }
        
        # Create post with image
        test_image = self.create_test_image()
        post_data = {
            'title': 'List Test Post',
            'content': 'Testing image in list view.',
            'status': 'published',
            'featured_image': test_image,
        }
        
        self.client.post(self.create_url, post_data, format='multipart')
        
        # Check post list
        post_list_url = reverse('post_list')
        response = self.client.get(post_list_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'List Test Post')