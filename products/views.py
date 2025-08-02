from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.forms import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import generics, status
from rest_framework.exceptions import NotFound
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissionsUsers import (
    IsSuperAdmin, IsSeller, IsAdmin,
    IsSuperAdminOrAdmin, IsBuyerOrSeller
)

from .models import (
    Category, Product, ProductImage, WishlistItem,
    Wishlist, Cart, CartItem, SaleEvent, ProductSale
)

from .permissions import IsSellerOrAdmin
from .serializers import (
    ProductSerializer, CartSerializer, CartItemSerializer,
    ProductLanguageSerializer, SaleEventSerializer,
    ProductSaleSerializer, WishlistItemSerializer,
    WishlistSerializer, CreateProductSaleSerializer,
    UpdateProductSaleSerializer, ProductDiscountSerializer,
    CategorySerializer
)

class CreateCategoryView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def post(self, request):
        name_ar = request.data.get('name_ar')
        name_en = request.data.get('name_en')
        parent_id = request.data.get('parent_id')

        if not name_ar or not name_en:
            return Response({'error': 'يجب إدخال الاسم بالعربي والإنجليزي.'}, status=400)

        # Check for duplicate names at the same level
        duplicate_filter = Q(name_ar__iexact=name_ar) | Q(name_en__iexact=name_en)
        if parent_id:
            duplicate_filter &= Q(parent_id=parent_id)
        else:
            duplicate_filter &= Q(parent__isnull=True)

        if Category.objects.filter(duplicate_filter).exists():
            return Response({'error': 'اسم الفئة موجود مسبقًا في هذا المستوى.'}, status=400)

        parent = None
        if parent_id:
            try:
                parent = Category.objects.get(pk=parent_id)
                
                # Prevent selecting a child category as parent
                if parent.parent:
                    return Response(
                        {'error': 'لا يمكن اختيار قسم فرعي كقسم رئيسي.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                    
            except Category.DoesNotExist:
                return Response({'error': 'الفئة الرئيسية غير موجودة.'}, status=404)

        category = Category.objects.create(
            name_ar=name_ar,
            name_en=name_en,
            parent=parent
        )
        serializer = CategorySerializer(category)
        return Response({'message': 'تم إنشاء الفئة بنجاح.', 'category': serializer.data}, status=201)

class UpdateCategoryView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def put(self, request, pk):
        try:
            category = Category.objects.get(pk=pk)
        except Category.DoesNotExist:
            return Response({'error': 'الفئة غير موجودة.'}, status=404)

        name_ar = request.data.get('name_ar')
        name_en = request.data.get('name_en')
        parent_id = request.data.get('parent_id')

        if not name_ar or not name_en:
            return Response({'error': 'الاسم العربي والإنجليزي مطلوبان.'}, status=400)

        # Check for duplicate names at the same level
        duplicate_filter = (Q(name_ar__iexact=name_ar) | Q(name_en__iexact=name_en)) & ~Q(pk=pk)
        if parent_id:
            duplicate_filter &= Q(parent_id=parent_id)
        else:
            duplicate_filter &= Q(parent__isnull=True)

        if Category.objects.filter(duplicate_filter).exists():
            return Response({'error': 'اسم الفئة موجود مسبقًا في هذا المستوى.'}, status=400)

        # Prevent making a category its own parent
        if parent_id and int(parent_id) == pk:
            return Response({'error': 'لا يمكن جعل الفئة ابنة لنفسها.'}, status=400)

        # Prevent changing parent if category has children
        if category.children.exists() and parent_id and category.parent_id != int(parent_id):
            return Response({'error': 'لا يمكن تغيير المستوى لفئة لديها أقسام فرعية.'}, status=400)

        parent = None
        if parent_id:
            try:
                parent = Category.objects.get(pk=parent_id)
                
                # NEW VALIDATION: Prevent selecting a child category as parent
                if parent.parent:
                    return Response(
                        {'error': 'لا يمكن اختيار قسم فرعي كقسم رئيسي.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                    
                # NEW VALIDATION: Prevent circular relationships
                if self._is_circular_relationship(category, parent):
                    return Response(
                        {'error': 'لا يمكن إنشاء علاقة دائرية بين الأقسام.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                    
            except Category.DoesNotExist:
                return Response({'error': 'الفئة الرئيسية غير موجودة.'}, status=404)

        category.name_ar = name_ar
        category.name_en = name_en
        category.parent = parent
        category.save()

        return Response({'message': 'تم تحديث الفئة بنجاح.'})
    
    def _is_circular_relationship(self, category, potential_parent):
        """
        Check if assigning potential_parent as parent would create a circular relationship
        """
        # If the potential parent is already a child of this category
        current = potential_parent
        while current is not None:
            if current.id == category.id:
                return True
            current = current.parent
        return False
    
class DeleteCategoryView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def delete(self, request, pk):
        try:
            category = Category.objects.get(pk=pk)
            
            # Prevent deletion if category has children
            if category.children.exists():
                return Response({'error': 'لا يمكن حذف فئة لديها أقسام فرعية.'}, status=400)
                
            # Prevent deletion if category has products
            if category.products.exists():
                return Response({'error': 'لا يمكن حذف فئة تحتوي على منتجات.'}, status=400)
                
            category.delete()
            return Response({'message': 'تم حذف الفئة بنجاح.'})
        except Category.DoesNotExist:
            return Response({'error': 'الفئة غير موجودة.'}, status=404)

class LocalizedCategoryListView(APIView):
    permission_classes = []  # Accessible to everyone
    
    def get(self, request):
        language = request.headers.get('Accept-Language', 'ar').lower()
        if language not in ['ar', 'en']:
            language = 'ar'

        # Get all parent categories with their children
        parent_categories = Category.objects.filter(parent__isnull=True).prefetch_related('children')
        
        results = []
        for parent in parent_categories:
            parent_data = {
                'id': parent.id,
                'name': parent.name_ar if language == 'ar' else parent.name_en,
                'children': []
            }
            
            for child in parent.children.all():
                parent_data['children'].append({
                    'id': child.id,
                    'name': child.name_ar if language == 'ar' else child.name_en
                })
            
            results.append(parent_data)

        return Response(results)

class ParentCategoryListView(APIView):
    permission_classes = []
    
    def get(self, request):
        lang = request.headers.get('Accept-Language', 'ar').lower()
        if lang not in ['ar', 'en']:
            lang = 'ar'
        
        parent_categories = Category.objects.filter(parent__isnull=True)
        results = []
        
        for cat in parent_categories:
            results.append({
                'id': cat.id,
                'name': cat.name_ar if lang == 'ar' else cat.name_en,
                'has_children': cat.children.exists()
            })
        
        return Response(results)

class ChildCategoryListView(APIView):
    permission_classes = []
    
    def get(self, request, parent_id):
        lang = request.headers.get('Accept-Language', 'ar').lower()
        if lang not in ['ar', 'en']:
            lang = 'ar'
        
        parent = get_object_or_404(Category, id=parent_id)
        children = parent.children.all()
        
        results = []
        for child in children:
            results.append({
                'id': child.id,
                'name': child.name_ar if lang == 'ar' else child.name_en
            })
        
        return Response(results)

class ProductCreateView(APIView):
    permission_classes = [IsAuthenticated, IsSeller]

    def post(self, request, category_id):

        quantity = request.data.get('quantity', 1)  # Default to 1 if not provided

        try:
            quantity = int(quantity)
            if quantity < 0:
                return Response(
                    {"error": "Quantity must be a positive number"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except (ValueError, TypeError):
            return Response(
                {"error": "Invalid quantity value"},
                status=status.HTTP_400_BAD_REQUEST
            )


        # التحقق من وجود الفئة
        category = get_object_or_404(Category, id=category_id)
        
        # Changed from if not category.is_child:
        if not category.parent:  # This checks if it's a parent category
            return Response(
                {"error": "يجب اختيار قسم فرعي وليس رئيسي"},
                status=status.HTTP_400_BAD_REQUEST
            )


        # التحقق من المدخلات الأساسية
        name_ar = request.data.get('name_ar')
        name_en = request.data.get('name_en')
        description_ar = request.data.get('description_ar')
        description_en = request.data.get('description_en')
        price = request.data.get('price')
        images = request.FILES.getlist('images')

        if not all([name_ar, name_en, description_ar, description_en, price]):
            return Response({"error": "جميع الحقول النصية مطلوبة"}, status=status.HTTP_400_BAD_REQUEST)

        if len(images) == 0:
            return Response({"error": "يجب رفع صورة واحدة على الأقل للمنتج"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            price = float(price)
            if price <= 0:
                return Response({"error": "يجب أن يكون السعر رقمًا موجبًا"}, status=status.HTTP_400_BAD_REQUEST)
        except ValueError:
            return Response({"error": "السعر يجب أن يكون رقمًا صحيحًا أو عشريًا"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                product = Product.objects.create(
                    category=category,
                    seller=request.user,
                    quantity=quantity,
                    name_ar=name_ar,
                    name_en=name_en,
                    description_ar=description_ar,
                    description_en=description_en,
                    price=price,
                    is_approved=False
                )

                for image in images:
                    if not image.content_type.startswith('image/'):
                        raise ValidationError("يجب رفع ملفات صور فقط")
                    ProductImage.objects.create(product=product, image=image)

                serializer = ProductSerializer(product)
                return Response({
                    "message": "تم إنشاء المنتج بنجاح بانتظار الموافقة",
                    "product": serializer.data
                }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class ProductApprovalView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdminOrAdmin]
    
    def post(self, request, product_id):
        """Approve a product"""
        product = get_object_or_404(Product, id=product_id)
        
        if product.is_approved:
            return Response(
                {"error": "Product is already approved"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        product.is_approved = True
        product.approved_by = request.user
        product.approved_at = timezone.now()
        product.save()
        
        return Response(
            {"message": "Product approved successfully"},
            status=status.HTTP_200_OK
        )

class ProductDisapprovalView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdminOrAdmin]
    
    def post(self, request, product_id):
        """Disapprove a product with reason"""
        product = get_object_or_404(Product, id=product_id)
        reason_ar = request.data.get('reason_ar', '').strip()
        reason_en = request.data.get('reason_en', '').strip()

        if not reason_ar:
            return Response(
                {"error": "السبب مطلوب باللغة العربي reason_ar"},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not reason_en:
            return Response(
                {"error": "the reason is requiered in english language reason_en"},
                status=status.HTTP_400_BAD_REQUEST
            )
        # Store the old approval status to check if it changed
        was_approved = product.is_approved
        
        # Update product fields
        product.is_approved = False
        product.disapproval_reason_ar = reason_ar
        product.disapproval_reason_en = reason_en
        product.approved_by = request.user
        product.approved_at = timezone.now()
        product.save()
        
        # Manually trigger notification if status changed
        if was_approved != product.is_approved:
            from notifications.models import Notification
            Notification.objects.create(
                user=product.seller,
                notification_type='product_disapproved',
                message_ar=f"تم رفض منتجك: {product.name_ar}. السبب: {reason_ar}",
                message_en=f"Your product was rejected: {product.name_en}. Reason: {reason_en}",
                content_object=product,
                extra_data={'disapproval_reason': reason_ar}
            )
        
        return Response(
            {
                "message": "Product disapproved",
                "reason": reason_ar
            },
            status=status.HTTP_200_OK
        )
    
class SellerUnapprovedProductsView(APIView): 
    permission_classes = [IsAuthenticated, IsSeller]
    
    def get(self, request):
        # الحصول على اللغة من الهيدر مع جعل العربية الافتراضية
        lang = request.headers.get('Accept-Language', 'ar').lower()
        
        # إذا كانت اللغة غير معروفة أو غير مدعومة، نستخدم العربية
        if lang not in ['ar', 'en']:
            lang = 'ar'
        
        # الحصول على منتجات البائع غير الموافق عليها مع معلومات الفئة
        products = Product.objects.filter(
            seller=request.user,
            is_approved=False
        ).select_related('category').prefetch_related('images')
        
        # استخدام السيريالايزر مع تحديد اللغة
        serializer = ProductLanguageSerializer(products, many=True, context={'lang': lang})
        return Response(serializer.data)    

class SellerApprovedProductsView(APIView):
    permission_classes = [IsAuthenticated, IsSeller]
    
    def get(self, request):
        # الحصول على اللغة من الهيدر مع جعل العربية الافتراضية
        lang = request.headers.get('Accept-Language', 'ar').lower()
        
        # التحقق من اللغات المدعومة (العربية والإنجليزية فقط)
        if lang not in ['ar', 'en']:
            lang = 'ar'  # نستخدم العربية إذا كانت اللغة غير معروفة
        
        # الحصول على منتجات البائع الموافق عليها مع تحسين الأداء
        products = Product.objects.filter(
            seller=request.user,
            is_approved=True,
        ).select_related('category').prefetch_related('images')
        
        # استخدام السيريالايزر مع تحديد اللغة
        serializer = ProductLanguageSerializer(products, many=True, context={
            'lang': lang,
            'request': request,
            'show_discount_details': True  # Show full discount info for seller
        })
        return Response(serializer.data)
    
class SellerProductDeleteView(APIView):
    permission_classes = [IsAuthenticated, IsSeller]
    
    def delete(self, request, product_id):
        # الحصول على المنتج والتأكد من أنه ملك للبائع
        product = get_object_or_404(Product, id=product_id)
        
        if product.seller != request.user:
            return Response(
                {"error": "ليس لديك صلاحية حذف هذا المنتج"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        product.delete()
        return Response(
            {"message": "تم حذف المنتج بنجاح"},
            status=status.HTTP_204_NO_CONTENT
        )    

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
    
    def paginate_queryset(self, queryset, request, view=None):
        """
        Add page number validation and total pages count
        """
        self.request = request  # Store the request object for link generation
        page_size = self.get_page_size(request)
        paginator = self.django_paginator_class(queryset, page_size)
        page_number = request.query_params.get(self.page_query_param, 1)
        
        try:
            page_number = int(page_number)
        except (TypeError, ValueError):
            raise NotFound("Invalid page number. Please provide a positive integer.")
            
        if page_number < 1:
            raise NotFound("Invalid page number. Pages start from 1.")
            
        try:
            self.page = paginator.page(page_number)
        except:
            raise NotFound("Invalid page number. Page does not exist.")
            
        self.total_pages = paginator.num_pages
        return list(self.page)
    
    def get_paginated_response(self, data):
        """
        Include total pages in response with proper request context for links
        """
        return Response({
            'count': self.page.paginator.count,
            'total_pages': self.total_pages,
            'current_page': self.page.number,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data
        })

class ProductListView(APIView):
    permission_classes = []  # Accessible to anyone
    
    def get(self, request):
        lang = request.headers.get('Accept-Language', 'ar').lower()
        if lang not in ['ar', 'en']:
            lang = 'ar'
        
        # Get all filter parameters
        min_price = request.query_params.get('min_price')
        max_price = request.query_params.get('max_price')
        min_rating = request.query_params.get('min_rating')
        max_rating = request.query_params.get('max_rating')
        category_id = request.query_params.get('category_id')
        parent_category_id = request.query_params.get('parent_category_id')
        min_quantity = request.query_params.get('min_quantity')
        max_quantity = request.query_params.get('max_quantity')
        in_stock = request.query_params.get('in_stock')
        has_discount = request.query_params.get('has_discount')
        
        # Get sorting parameters
        sort_by = request.query_params.get('sort_by', '-created_at')  # Default: newest first
        sort_direction = request.query_params.get('sort_direction', 'desc')  # Default: descending
        
        # Validate sort options
        valid_sort_fields = ['price', 'created_at', 'rating']
        if sort_by not in valid_sort_fields:
            sort_by = 'created_at'
        
        # Validate sort direction
        sort_direction = sort_direction.lower()
        if sort_direction not in ['asc', 'desc']:
            sort_direction = 'desc'
        
        # Build sort parameter
        sort_prefix = '' if sort_direction == 'asc' else '-'
        sort_param = f"{sort_prefix}{sort_by}"
        
        # Start with base queryset
        products = Product.objects.filter(is_approved=True)
        
        # Apply category filters
        if category_id:
            products = products.filter(category_id=category_id)
        elif parent_category_id:
            products = products.filter(category__parent_id=parent_category_id)
        
        # Apply price filters
        if min_price:
            try:
                products = products.filter(price__gte=float(min_price))
            except (ValueError, TypeError):
                pass
                
        if max_price:
            try:
                products = products.filter(price__lte=float(max_price))
            except (ValueError, TypeError):
                pass
        
        # Apply rating filters
        if min_rating:
            try:
                products = products.filter(rating__gte=float(min_rating))
            except (ValueError, TypeError):
                pass
                
        if max_rating:
            try:
                products = products.filter(rating__lte=float(max_rating))
            except (ValueError, TypeError):
                pass

        # Apply quantity filters
        if min_quantity:
            try:
                products = products.filter(quantity__gte=int(min_quantity))
            except (ValueError, TypeError):
                pass
                
        if max_quantity:
            try:
                products = products.filter(quantity__lte=int(max_quantity))
            except (ValueError, TypeError):
                pass
                
        # Apply in-stock filter
        if in_stock and in_stock.lower() in ['true', '1', 'yes']:
            products = products.filter(quantity__gt=0)

        # Apply discount filter
        if has_discount and has_discount.lower() in ['true', '1', 'yes']:
            now = timezone.now()
            products = products.filter(
                Q(has_standalone_discount=True) &
                Q(standalone_discount_percentage__isnull=False) &
                (
                    Q(standalone_discount_start__isnull=True) | 
                    Q(standalone_discount_start__lte=now)
                ) &
                (
                    Q(standalone_discount_end__isnull=True) | 
                    Q(standalone_discount_end__gte=now)
                )
            )

        # Apply sorting
        products = products.order_by(sort_param)
        
        # Pagination with proper request context
        paginator = StandardResultsSetPagination()
        result_page = paginator.paginate_queryset(products, request)
        
        serializer = ProductLanguageSerializer(result_page, many=True, context={
            'lang': lang,
            'request': request,
            'show_discount_price': True
        })
        
        return paginator.get_paginated_response(serializer.data)
    
class ProductDetailView(APIView):
    permission_classes = []  # Accessible to anyone
    
    def get(self, request, pk):
        lang = request.headers.get('Accept-Language', 'ar').lower()
        if lang not in ['ar', 'en']:
            lang = 'ar'
        
        product = get_object_or_404(Product, pk=pk, is_approved=True)
        serializer = ProductLanguageSerializer(product, context={
            'lang': lang,
            'request': request,
            'show_discount_price': True
        })
        return Response(serializer.data)

class CategoryProductsView(APIView):
    permission_classes = []
    
    def get(self, request, category_id):
        lang = request.headers.get('Accept-Language', 'ar').lower()
        if lang not in ['ar', 'en']:
            lang = 'ar'
        
        category = get_object_or_404(Category, pk=category_id)
        
        # If it's a parent category, get products from all its children
        if category.is_parent:
            products = Product.objects.filter(
                category__in=category.children.all(),
                is_approved=True
            ).order_by('-created_at')
        else:
            # If it's a child category, get its products directly
            products = Product.objects.filter(
                category=category,
                is_approved=True
            ).order_by('-created_at')
        
        serializer = ProductLanguageSerializer(products, many=True, context={
            'lang': lang,
            'request': request
        })
        return Response(serializer.data)
    
class ProductSearchView(APIView):
    permission_classes = []
    
    def get(self, request):
        lang = request.headers.get('Accept-Language', 'ar').lower()
        if lang not in ['ar', 'en']:
            lang = 'ar'
        
        query = request.query_params.get('q', '').strip()
        if not query:
            return Response({"error": "Search query is required"}, status=400)
        
        # Search in both Arabic and English names/descriptions
        products = Product.objects.filter(
            Q(name_ar__icontains=query) | 
            Q(description_ar__icontains=query) |
            Q(name_en__icontains=query) | 
            Q(description_en__icontains=query),
            
            is_approved=True
        )
        
        serializer = ProductLanguageSerializer(products, many=True, context={
            'lang': lang,
            'request': request
        })
        return Response(serializer.data)

class UpdateProductQuantityView(APIView):
    permission_classes = [IsAuthenticated, IsSeller]
    
    def patch(self, request, product_id):
        product = get_object_or_404(Product, id=product_id, seller=request.user)
        
        quantity = request.data.get('quantity')
        if quantity is None:
            return Response(
                {"error": "Quantity field is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            quantity = int(quantity)
            if quantity < 0:
                return Response(
                    {"error": "Quantity must be a positive number"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except (ValueError, TypeError):
            return Response(
                {"error": "Quantity must be a valid integer"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        product.quantity = product.quantity + quantity
        product.save()
        
        return Response({
            "message": "Product quantity updated successfully",
            "product_id": product.id,
            "new_quantity": product.quantity
        })

class CartView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cart, _ = Cart.objects.get_or_create(user=request.user)
        serializer = CartSerializer(cart)
        return Response(serializer.data)

class AddToCartView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        product_id = request.data.get('product_id')
        quantity = request.data.get('quantity', 1)

        try:
            product = Product.objects.get(id=product_id, is_approved=True)
        except Product.DoesNotExist:
            return Response(
                {"error": "Product not found or not approved"},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            quantity = int(quantity)
            if quantity <= 0:
                raise ValueError
        except (ValueError, TypeError):
            return Response(
                {"error": "Quantity must be a positive integer"},
                status=status.HTTP_400_BAD_REQUEST
            )

        cart, _ = Cart.objects.get_or_create(user=request.user)

        try:
            with transaction.atomic():
                # Check available quantity
                if quantity > product.quantity:
                    return Response(
                        {"error": f"Only {product.quantity} available in stock"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                cart_item, created = CartItem.objects.get_or_create(
                    cart=cart,
                    product=product,
                    defaults={'quantity': quantity}
                )

                if not created:
                    new_quantity = cart_item.quantity + quantity
                    if new_quantity > product.quantity:
                        return Response(
                            {"error": f"Cannot add {quantity} more (only {product.quantity - cart_item.quantity} available)"},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    cart_item.quantity = new_quantity
                    cart_item.save()

                serializer = CartSerializer(cart)
                return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

class UpdateCartItemView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, item_id):
        quantity = request.data.get('quantity')

        try:
            quantity = int(quantity)
            if quantity <= 0:
                raise ValueError
        except (ValueError, TypeError):
            return Response(
                {"error": "Quantity must be a positive integer"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            cart_item = CartItem.objects.get(
                id=item_id,
                cart__user=request.user
            )
        except CartItem.DoesNotExist:
            return Response(
                {"error": "Item not found in your cart"},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            with transaction.atomic():
                if quantity > cart_item.product.quantity:
                    return Response(
                        {"error": f"Only {cart_item.product.quantity} available in stock"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                cart_item.quantity = quantity
                cart_item.save()
                
                serializer = CartSerializer(cart_item.cart)
                return Response(serializer.data)

        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

class RemoveFromCartView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, item_id):
        try:
            cart_item = CartItem.objects.get(
                id=item_id,
                cart__user=request.user
            )
            cart_item.delete()
            return Response(
                {"message": "Item removed from cart"},
                status=status.HTTP_204_NO_CONTENT
            )
        except CartItem.DoesNotExist:
            return Response(
                {"error": "Item not found in your cart"},
                status=status.HTTP_404_NOT_FOUND
            )

class WishlistView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        wishlist, _ = Wishlist.objects.get_or_create(user=request.user)
        serializer = WishlistSerializer(wishlist)
        return Response(serializer.data)

class AddToWishlistView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        product_id = request.data.get('product_id')
        
        try:
            product = Product.objects.get(id=product_id, is_approved=True)
        except Product.DoesNotExist:
            return Response(
                {"error": "Product not found or not approved"},
                status=status.HTTP_404_NOT_FOUND
            )

        wishlist, _ = Wishlist.objects.get_or_create(user=request.user)

        if WishlistItem.objects.filter(wishlist=wishlist, product=product).exists():
            return Response(
                {"error": "Product already in wishlist"},
                status=status.HTTP_400_BAD_REQUEST
            )

        WishlistItem.objects.create(wishlist=wishlist, product=product)
        
        serializer = WishlistSerializer(wishlist)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class RemoveFromWishlistView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, item_id):
        try:
            item = WishlistItem.objects.get(
                id=item_id,
                wishlist__user=request.user
            )
            item.delete()
            return Response(
                {"message": "Item removed from wishlist"},
                status=status.HTTP_204_NO_CONTENT
            )
        except WishlistItem.DoesNotExist:
            return Response(
                {"error": "Item not found in your wishlist"},
                status=status.HTTP_404_NOT_FOUND
            )

class MoveToCartView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, item_id):
        try:
            wishlist_item = WishlistItem.objects.get(
                id=item_id,
                wishlist__user=request.user
            )
            
            cart, _ = Cart.objects.get_or_create(user=request.user)
            
            # Check if product already in cart
            cart_item, created = CartItem.objects.get_or_create(
                cart=cart,
                product=wishlist_item.product,
                defaults={'quantity': 1}
            )
            
            if not created:
                if cart_item.quantity < cart_item.product.quantity:
                    cart_item.quantity += 1
                    cart_item.save()
            
            wishlist_item.delete()
            
            return Response(
                {
                    "message": "Item moved to cart",
                    "cart": CartSerializer(cart).data,
                    "wishlist": WishlistSerializer(wishlist_item.wishlist).data
                },
                status=status.HTTP_200_OK
            )
            
        except WishlistItem.DoesNotExist:
            return Response(
                {"error": "Item not found in your wishlist"},
                status=status.HTTP_404_NOT_FOUND
            )

class ActiveSaleEventListView(APIView):
    permission_classes = []

    def get(self, request):
        now = timezone.now()
        events = SaleEvent.objects.filter(
            start_date__lte=now,
            end_date__gte=now
        )
        
        # Handle language
        lang = request.headers.get('Accept-Language', 'en').lower()
        if lang not in ['ar', 'en']:
            lang = 'en'
        
        data = []
        for event in events:
            data.append({
                'id': event.id,
                'name': event.name_ar if lang == 'ar' else event.name_en,
                'description': event.description_ar if lang == 'ar' else event.description_en,
                'start_date': event.start_date,
                'end_date': event.end_date
            })
        
        return Response(data)

class ProductsInSaleView(APIView):
    permission_classes = []

    def get(self, request, sale_id):
        now = timezone.now()
        products = ProductSale.objects.filter(
            sale_event_id=sale_id,
            sale_event__start_date__lte=now,
            sale_event__end_date__gte=now
        ).select_related('product', 'sale_event')
        
        serializer = ProductSaleSerializer(products, many=True)
        return Response(serializer.data)

class CreateSaleEventView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request):
        serializer = SaleEventSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(created_by=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Seller endpoints
class SellerProductSaleListView(APIView):
    permission_classes = [IsAuthenticated, IsSeller]

    def get(self, request):
        sales = ProductSale.objects.filter(
            product__seller=request.user
        ).select_related('sale_event', 'product')
        serializer = ProductSaleSerializer(sales, many=True)
        return Response(serializer.data)

class CreateProductSaleView(APIView):
    permission_classes = [IsAuthenticated, IsSeller]

    def post(self, request):
        serializer = CreateProductSaleSerializer(
            data=request.data,
            context={'request': request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UpdateProductSaleView(APIView):
    permission_classes = [IsAuthenticated, IsSeller]

    def patch(self, request, pk):
        sale = get_object_or_404(ProductSale, pk=pk)
        serializer = UpdateProductSaleSerializer(
            sale,
            data=request.data,
            partial=True,
            context={'request': request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class DeleteProductSaleView(APIView):
    permission_classes = [IsAuthenticated, IsSeller]

    def delete(self, request, pk):
        sale = get_object_or_404(ProductSale, pk=pk, product__seller=request.user)
        sale.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class ProductDiscountView(APIView):
    permission_classes = [IsAuthenticated, IsSeller]
    
    def patch(self, request, pk):
        if not request.data:
            return Response(
                {"error": "No data provided for update"},
                status=status.HTTP_400_BAD_REQUEST
            )

        product = get_object_or_404(Product, pk=pk, seller=request.user)
        
        serializer = ProductDiscountSerializer(
            product,
            data=request.data,
            partial=True
        )
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            product = serializer.save()
            return Response(
                ProductSerializer(product).data,
                status=status.HTTP_200_OK
            )
        except ValidationError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from .models import SellerBlock, User



from django.db import transaction
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from .models import SellerBlock, User

class BlockSellerView(APIView):
    permission_classes = [IsAuthenticated, IsBuyerOrSeller]
    
    def post(self, request, seller_id):
        """
        حظر بائع معين
        """
        with transaction.atomic():
            if request.user.id == seller_id:
                return Response(
                    {"error": "لا يمكنك حظر نفسك"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            seller_to_block = get_object_or_404(User, id=seller_id)
            
            if not hasattr(seller_to_block, 'role'):
                return Response(
                    {"error": "المستخدم ليس لديه دور محدد"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if seller_to_block.role != 'seller':
                return Response(
                    {"error": "يمكن فقط حظر المستخدمين من نوع بائع"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if SellerBlock.objects.filter(
                blocker=request.user,
                blocked_seller=seller_to_block
            ).exists():
                return Response(
                    {"error": "لقد قمت بحظر هذا البائع مسبقًا"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            block = SellerBlock.objects.create(
                blocker=request.user,
                blocked_seller=seller_to_block
            )
            
            response_data = {
                "message": "تم حظر البائع بنجاح",
                "data": {
                    "id": block.id,
                    "blocker_id": block.blocker.id,
                    "blocker_username": block.blocker.username,
                    "blocked_seller_id": block.blocked_seller.id,
                    "blocked_seller_username": block.blocked_seller.username,
                    "created_at": block.created_at.strftime("%Y-%m-%d %H:%M:%S")
                }
            }
            
            return Response(response_data, status=status.HTTP_201_CREATED)

    def delete(self, request, seller_id):
        """
        إلغاء حظر بائع
        """
        with transaction.atomic():
            block = get_object_or_404(
                SellerBlock,
                blocker=request.user,
                blocked_seller_id=seller_id
            )
            block.delete()
            return Response(
                {"message": "تم إلغاء حظر البائع بنجاح"},
                status=status.HTTP_204_NO_CONTENT
            )


class BlockedSellersListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        blocked_relations = SellerBlock.objects.filter(
            blocker=request.user
        ).select_related('blocked_seller', 'blocked_seller__profile')
        
        blocked_data = []
        for block in blocked_relations:
            seller = block.blocked_seller
            profile = getattr(seller, 'profile', None)

            blocked_data.append({
                "id": seller.id,
                "first_name": seller.first_name,
                "last_name": seller.last_name,
                "address": seller.address if hasattr(seller, 'address') else None,
                "phone_number": seller.phone_number if hasattr(seller, 'phone_number') else None,
                "image": request.build_absolute_uri(profile.image.url) if profile and profile.image else None,
                "bio": profile.bio if profile else None,
                "blocked_at": block.created_at.strftime("%Y-%m-%d %H:%M:%S")
            })

        return Response({"blocked_sellers": blocked_data}, status=status.HTTP_200_OK)

class UnapprovedProductsView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdminOrAdmin]

    def get(self, request):
        lang = request.query_params.get('lang', 'ar')

        products = Product.objects.filter(is_approved=False).order_by('-created_at').select_related('category').prefetch_related('images')

        data = []
        for product in products:
            category = product.category
            category_name = category.name_en if lang == 'en' else category.name_ar

            # جلب روابط الصور كاملة
            images = [
                request.build_absolute_uri(image.image.url)
                for image in product.images.all()
            ]

            data.append({
                'id': product.id,
                'name': product.name_en if lang == 'en' else product.name_ar,
                'description': product.description_en if lang == 'en' else product.description_ar,
                'price': str(product.price),
                'category_id': category.id,
                'category_name': category_name,
                'images': images,
                'created_at': product.created_at.strftime('%Y-%m-%d %H:%M:%S')
            })

        return Response({'unapproved_products': data}, status=status.HTTP_200_OK)
