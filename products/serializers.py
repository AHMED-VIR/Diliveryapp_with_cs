# serializers.py
from rest_framework import serializers
from .models import Category,Wishlist,WishlistItem,SaleEvent,ProductSale
from .models import Product, ProductImage,Cart,CartItem
from rest_framework import serializers
from django.utils import timezone

class ProductLanguageSerializer(serializers.ModelSerializer):
    category_name = serializers.SerializerMethodField()
    parent_category_name = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()
    current_price = serializers.SerializerMethodField()
    has_active_discount = serializers.SerializerMethodField()
    discount_percentage = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'name_ar', 'name_en', 'description_ar', 'description_en',
            'price', 'current_price', 'category_id', 'category_name', 
            'parent_category_name', 'created_at', 'is_approved', 'images', 
            'disapproval_reason_ar', 'disapproval_reason_en', 'quantity',
            'has_active_discount', 'discount_percentage',"seller_id"
        ]

    def get_category_name(self, obj):
        lang = self.context.get('lang', 'ar')
        return obj.category.name_ar if lang == 'ar' else obj.category.name_en

    def get_parent_category_name(self, obj):
        lang = self.context.get('lang', 'ar')
        if obj.category.parent:
            return obj.category.parent.name_ar if lang == 'ar' else obj.category.parent.name_en
        return None

    def get_images(self, obj):
        request = self.context.get('request')
        if request:
            return [request.build_absolute_uri(img.image.url) for img in obj.images.all()]
        return [img.image.url for img in obj.images.all()]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        lang = self.context.get('lang', 'ar')
        
        # Handle language-specific fields
        if lang == 'en':
            data['name'] = data.pop('name_en')
            data['description'] = data.pop('description_en')
            data.pop('name_ar', None)
            data.pop('description_ar', None)
        else:
            data['name'] = data.pop('name_ar')
            data['description'] = data.pop('description_ar')
            data.pop('name_en', None)
            data.pop('description_en', None)
        
        # Clean up empty disapproval reasons
        if not data.get('disapproval_reason_ar'):
            data.pop('disapproval_reason_ar', None)
        if not data.get('disapproval_reason_en'):
            data.pop('disapproval_reason_en', None)

    def get_current_price(self, obj):
        return obj.current_price

    def get_has_active_discount(self, obj):
        now = timezone.now()
        return (obj.has_standalone_discount and 
                (not obj.standalone_discount_start or obj.standalone_discount_start <= now) and
                (not obj.standalone_discount_end or now <= obj.standalone_discount_end))

    def get_discount_percentage(self, obj):
        if self.get_has_active_discount(obj):
            return obj.standalone_discount_percentage
        return None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        lang = self.context.get('lang', 'ar')
        
        # Handle language-specific fields
        if lang == 'en':
            data['name'] = data.pop('name_en')
            data['description'] = data.pop('description_en')
            data.pop('name_ar', None)
            data.pop('description_ar', None)
        else:
            data['name'] = data.pop('name_ar')
            data['description'] = data.pop('description_ar')
            data.pop('name_en', None)
            data.pop('description_en', None)
        
        # Clean up empty fields
        for field in ['disapproval_reason_ar', 'disapproval_reason_en']:
            if not data.get(field):
                data.pop(field, None)
        
        # Only show discount percentage if there's an active discount
        if not data.get('has_active_discount'):
            data.pop('discount_percentage', None)
            
        return data

class CategorySerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = ['id', 'name_ar', 'name_en', 'parent', 'children', 'created_at']
    
    def get_children(self, obj):
        if obj.is_parent:
            children = obj.children.all()
            return CategorySerializer(children, many=True).data
        return []

class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'uploaded_at']

class ProductSerializer(serializers.ModelSerializer):
    images = ProductImageSerializer(many=True, read_only=True)
    category_name = serializers.SerializerMethodField()
    current_price = serializers.SerializerMethodField()
    has_active_discount = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = [
            'id', 'name_ar', 'name_en', 'description_ar', 'description_en',
            'price', 'current_price', 'category', 'category_name',
            'seller', 'is_approved', 'created_at', 'images',
            'has_active_discount', 'has_standalone_discount',
            'standalone_discount_percentage', 'standalone_discount_start',
            'standalone_discount_end', 'quantity'
        ]
    
    def get_current_price(self, obj):
        return obj.current_price
    
    def get_has_active_discount(self, obj):
        now = timezone.now()
        return (obj.has_standalone_discount and 
                (not obj.standalone_discount_start or obj.standalone_discount_start <= now) and
                (not obj.standalone_discount_end or now <= obj.standalone_discount_end))

    def get_category_name(self, obj):
        lang = self.context.get('lang', 'ar')
        return obj.category.name_ar if lang == 'ar' else obj.category.name_en
  
class CartItemSerializer(serializers.ModelSerializer):
    product = ProductLanguageSerializer()
    max_available = serializers.SerializerMethodField()
    current_price = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = [
            'id', 'product', 'quantity', 'added_at', 
            'max_available', 'current_price'
        ]
        read_only_fields = fields

    def get_max_available(self, obj):
        return obj.product.quantity
        
    def get_current_price(self, obj):
        return obj.product.current_price
    
class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True)
    total_items = serializers.IntegerField(read_only=True)
    total_price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True
    )
    total_discount = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ['id', 'items', 'total_items', 'total_price', 'total_discount']
        
    def get_total_discount(self, obj):
        total = 0
        for item in obj.items.all():
            if item.product.has_active_discount:
                discount_amount = item.product.price - item.product.current_price
                total += discount_amount * item.quantity
        return total

class WishlistItemSerializer(serializers.ModelSerializer):
    product = serializers.SerializerMethodField()
    has_discount = serializers.SerializerMethodField()
    discount_percentage = serializers.SerializerMethodField()
    current_price = serializers.SerializerMethodField()

    class Meta:
        model = WishlistItem
        fields = ['id', 'product', 'added_at', 'has_discount', 'discount_percentage', 'current_price']
        read_only_fields = fields

    def get_product(self, obj):
        # Use ProductLanguageSerializer for product details
        return ProductLanguageSerializer(
            obj.product,
            context=self.context
        ).data

    def get_has_discount(self, obj):
        return obj.product.has_active_discount

    def get_discount_percentage(self, obj):
        return obj.product.active_discount_percentage

    def get_current_price(self, obj):
        if obj.product.has_active_discount:
            discount = obj.product.active_discount_percentage or 0
            return obj.product.price * (100 - discount) / 100
        return obj.product.price

class WishlistSerializer(serializers.ModelSerializer):
    items = WishlistItemSerializer(many=True)

    class Meta:
        model = Wishlist
        fields = ['id', 'items']

class SaleEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = SaleEvent
        fields = [
            'id', 'name_ar', 'name_en', 'description_ar', 'description_en',
            'start_date', 'end_date', 'is_active', 'created_at'
        ]
        read_only_fields = ['is_active', 'created_by', 'created_at']

class ProductSaleSerializer(serializers.ModelSerializer):
    product = ProductLanguageSerializer(read_only=True)
    sale_event = SaleEventSerializer(read_only=True)
    discounted_price = serializers.SerializerMethodField()
    
    class Meta:
        model = ProductSale
        fields = [
            'id', 'product', 'sale_event', 'discount_percentage',
            'discounted_price', 'is_active'
        ]
    
    def get_discounted_price(self, obj):
        return obj.product.price * (100 - obj.discount_percentage) / 100

class CreateProductSaleSerializer(serializers.ModelSerializer):
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all()
    )
    sale_event = serializers.PrimaryKeyRelatedField(
        queryset=SaleEvent.objects.filter(is_active=True)
    )

    class Meta:
        model = ProductSale
        fields = ['product', 'sale_event', 'discount_percentage']
    
    def validate(self, data):
        # Ensure product belongs to seller
        if self.context['request'].user != data['product'].seller:
            raise serializers.ValidationError(
                {"error": "You can only add your own products to sales"}
            )
        
        # Validate no duplicate product in same sale
        if ProductSale.objects.filter(
            product=data['product'],
            sale_event=data['sale_event']
        ).exists():
            raise serializers.ValidationError(
                {"error": "This product is already in the sale"}
            )
        
        return data
    
    def create(self, validated_data):
        sale_event = validated_data['sale_event']
        return ProductSale.objects.create(
            product=validated_data['product'],
            sale_event=sale_event,
            discount_percentage=validated_data['discount_percentage'],
            start_date=sale_event.start_date,
            end_date=sale_event.end_date
        )
    
class UpdateProductSaleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductSale
        fields = ['discount_percentage']  # Only allow updating discount percentage
    
    def validate(self, data):
        # Get the existing product from the instance
        product = self.instance.product
        if self.context['request'].user != product.seller:
            raise serializers.ValidationError(
                {"error": "You can only update your own product sales"}
            )
        return data
    
class ProductDiscountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = [
            'has_standalone_discount',
            'standalone_discount_percentage',
            'standalone_discount_start',
            'standalone_discount_end'
        ]
        
    def validate(self, data):
        # Check if product is in an admin sale
        if self.instance:
            now = timezone.now()
            in_admin_sale = self.instance.sales.filter(
                sale_event__created_by__is_staff=True,
                sale_event__start_date__lte=now,
                sale_event__end_date__gte=now
            ).exists()
            
            if in_admin_sale and data.get('has_standalone_discount', False):
                raise serializers.ValidationError(
                    "Cannot add standalone discount - product is already in an admin sale"
                )
        
        # Existing validation rules
        if data.get('has_standalone_discount'):
            if 'standalone_discount_percentage' not in data:
                raise serializers.ValidationError(
                    {"standalone_discount_percentage": "This field is required when enabling discount"}
                )
            
            if not (1 <= data['standalone_discount_percentage'] <= 100):
                raise serializers.ValidationError(
                    {"standalone_discount_percentage": "Discount percentage must be between 1 and 100"}
                )
            
            start = data.get('standalone_discount_start')
            end = data.get('standalone_discount_end')
            if start and end and start >= end:
                raise serializers.ValidationError(
                    {"standalone_discount_end": "Discount end date must be after start date"}
                )
        
        return data