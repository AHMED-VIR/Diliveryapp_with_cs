from django.urls import path
from .views import (
    CreateCategoryView,
    UpdateCategoryView,
    DeleteCategoryView,LocalizedCategoryListView,
    SellerUnapprovedProductsView,
    SellerApprovedProductsView,
    SellerProductDeleteView,ProductCreateView,BlockSellerView,
    BlockedSellersListView,UnapprovedProductsView,ProductApprovalView,ProductDisapprovalView,ProductListView,
    ProductDetailView,
    CategoryProductsView,
    ProductSearchView,
    ParentCategoryListView,
    ChildCategoryListView,
    UpdateProductQuantityView,
    CartView,
    AddToCartView,
    UpdateCartItemView,
    RemoveFromCartView,
    WishlistView,
    AddToWishlistView,
    RemoveFromWishlistView,
    MoveToCartView,
    CreateSaleEventView,
    CreateProductSaleView,
    UpdateProductSaleView,
    DeleteProductSaleView,
    ActiveSaleEventListView,
    ProductsInSaleView,
    SellerProductSaleListView,
    ProductDiscountView
)
urlpatterns = [
    path('LocalizedCategoryList/', LocalizedCategoryListView.as_view(), name='localized-category-list'),##  عرض الفئات حسب اللغة من الهيدر لاي شخص
    path('CreateCategory/', CreateCategoryView.as_view(), name='category-create'),
    path('UpdateCategory/<int:pk>/', UpdateCategoryView.as_view(), name='category-update'),
    path('DeleteCategory/<int:pk>/', DeleteCategoryView.as_view(), name='category-delete'),
    path('ProductCreate/<int:category_id>/', ProductCreateView.as_view(), name='ProductCreate'),##  اضافة منتج
    path('sellerproductsUnapproved/', SellerUnapprovedProductsView.as_view()),## عرض المنتجات الغير موافق عليها الخاصة بالبائع
    path('sellerproductsApproved/', SellerApprovedProductsView.as_view()),## عرض المنتجات  الموافق عليها الخاصة بالبائع
    path('sellerproductsDelete/<int:product_id>/', SellerProductDeleteView.as_view()),## حذف منتج
    path('blockseller/<int:seller_id>/', BlockSellerView.as_view(), name='block-seller'),
    path('blockedsellersList/', BlockedSellersListView.as_view(), name='list-blocked-sellers'),
    path('UnapprovedProductsForAdmins/', UnapprovedProductsView.as_view(), name='UnapprovedProductsForAdmins'),## عرض المنتجات الغير موافق عليها للادمنز
    path('approve/<int:product_id>/', 
         ProductApprovalView.as_view(), 
         name='product-approve'),
    path('disapprove/<int:product_id>/', 
         ProductDisapprovalView.as_view(), 
         name='product-disapprove'),
    path('', ProductListView.as_view(), name='product-list'),  # List all approved products
    path('<int:pk>/', ProductDetailView.as_view(), name='product-detail'),  # Single product
    path('category/<int:category_id>/products/', CategoryProductsView.as_view(), name='category-products'),
    path('search/', ProductSearchView.as_view(), name='product-search'),
    path('categories/parents/', ParentCategoryListView.as_view(), name='parent-categories'),
    path('categories/children/<int:parent_id>/', ChildCategoryListView.as_view(), name='child-categories'),
    path('update-quantity/<int:product_id>/', UpdateProductQuantityView.as_view(), name='update-product-quantity'),
    path('cart/', CartView.as_view(), name='cart'),
    path('cart/add/', AddToCartView.as_view(), name='add-to-cart'),
    path('cart/update/<int:item_id>/', UpdateCartItemView.as_view(), name='update-cart-item'),
    path('cart/remove/<int:item_id>/', RemoveFromCartView.as_view(), name='remove-from-cart'),
    path('wishlist/', WishlistView.as_view(), name='wishlist'),
    path('wishlist/add/', AddToWishlistView.as_view(), name='add-to-wishlist'),
    path('wishlist/remove/<int:item_id>/', RemoveFromWishlistView.as_view(), name='remove-from-wishlist'),
    path('wishlist/move-to-cart/<int:item_id>/', MoveToCartView.as_view(), name='move-to-cart'),
    path('sales/active/', ActiveSaleEventListView.as_view(), name='active-sales'),
    path('sales/<int:sale_id>/products/', ProductsInSaleView.as_view(), name='sale-products'),
    # Admin endpoints
    path('admin/sales/create/', CreateSaleEventView.as_view(), name='create-sale'),
    # Seller endpoints
    path('seller/sales/', SellerProductSaleListView.as_view(), name='seller-sales'),
    path('seller/sales/add/', CreateProductSaleView.as_view(), name='add-product-to-sale'),
    path('seller/sales/<int:pk>/update/', UpdateProductSaleView.as_view(), name='update-sale'),
    path('seller/sales/<int:pk>/delete/', DeleteProductSaleView.as_view(), name='delete-sale'),
    path('discounts/<int:pk>/discount/', 
         ProductDiscountView.as_view(), 
         name='product-discount'),
    ]


###...............