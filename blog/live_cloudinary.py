from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from .models import Post
import io
from PIL import Image
import cloudinary.uploader

class LiveCloudinaryIntegrationTest(TestCase):
    '''
    Real integration test with Cloudinary API.
    WARNING: This uploads real images to your Cloudinary account.
    Only run when you need to verify real integration.
    '''
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='livetest',
            password='LiveTest123!'
        )
        self.client.login(username='livetest', password='LiveTest123!')
        self.create_url = reverse('post_create')
        self.uploaded_public_ids = []
    
    def tearDown(self):
        # Clean up uploaded images from Cloudinary
        for public_id in self.uploaded_public_ids:
            try:
                cloudinary.uploader.destroy(public_id)
            except:
                pass
    
    def create_test_image(self):
        image = Image.new('RGB', (200, 200), color='blue')
        image_file = io.BytesIO()
        image.save(image_file, format='PNG')
        image_file.seek(0)
        return SimpleUploadedFile(
            name='live_test.png',
            content=image_file.read(),
            content_type='image/png'
        )
    
    def test_real_cloudinary_upload(self):
        '''Test actual upload to Cloudinary'''
        test_image = self.create_test_image()
        
        post_data = {
            'title': 'Live Cloudinary Test',
            'content': 'Testing real Cloudinary integration.',
            'status': 'published',
            'featured_image': test_image,
        }
        
        response = self.client.post(self.create_url, post_data, format='multipart')
        self.assertEqual(response.status_code, 302)
        
        # Verify post created with image
        post = Post.objects.get(title='Live Cloudinary Test')
        self.assertTrue(post.featured_image)
        self.assertTrue(post.featured_image.url)
        
        # Verify URL is from Cloudinary
        self.assertIn('cloudinary.com', post.featured_image.url)
        
        # Track for cleanup
        if hasattr(post.featured_image, 'public_id'):
            self.uploaded_public_ids.append(post.featured_image.public_id)
        
        # Verify image is accessible
        detail_url = reverse('post_detail', kwargs={'slug': post.slug})
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn(post.featured_image.url, response.content.decode())