from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
import os, uuid, re, random, io, base64
from datetime import datetime
from functools import wraps
from groq import Groq
import db
from icon_data import ICONS as _ICONS
from flask_wtf import CSRFProtect
from forms import LoginForm, RegisterForm
import qrcode
from werkzeug.utils import secure_filename
from authlib.integrations.flask_client import OAuth

# ── GROQ SETUP ────────────────────────────────────────────────────────────────
_groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))

app = Flask(__name__)
# Secure secret key — override via SECRET_KEY env variable in production
app.secret_key = os.environ.get('SECRET_KEY', 'change-this-before-deploying')
csrf = CSRFProtect(app)


# ── SQLITE INIT — creates threadverse.db + seeds data on first run ────────────
db.init_db()

# ── GOOGLE OAUTH ──────────────────────────────────────────────────────────────
# Set these environment variables before running:
#   GOOGLE_CLIENT_ID=your-google-client-id
#   GOOGLE_CLIENT_SECRET=your-google-client-secret
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.environ.get('GOOGLE_CLIENT_ID', ''),
    client_secret=os.environ.get('GOOGLE_CLIENT_SECRET', ''),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'},
)

# ── UPLOAD CONFIG ─────────────────────────────────────────────────────────────
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads', 'verification')
ALLOWED_DOC_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png'}
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10 MB max upload
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.template_global()
def icon(name, size=20, cls='', color='currentColor'):
    """Return a sized inline SVG icon for templates."""
    svg = _ICONS.get(name, _ICONS.get('sparkle', ''))
    if not svg:
        return ''
    styled = svg.replace(
        '<svg ',
        f'<svg width="{size}" height="{size}" style="display:inline-block;vertical-align:middle;flex-shrink:0;color:{color};" class="{cls}" '
    )
    return styled

@app.template_global()
def product_img(image_path):
    """Resolve product/store image paths used across templates."""
    if not image_path:
        return "https://via.placeholder.com/800x1000/f5f5f5/9aa0a6?text=ThreadVerse"

    img = str(image_path).strip()
    if img.startswith(('http://', 'https://', 'data:')):
        return img
    if img.startswith('/'):
        return img

    # Support existing DB values like "uploads/x.jpg" or "x.jpg".
    if img.startswith('uploads/'):
        return f"/static/{img}"
    return f"/static/uploads/{img}"

@app.template_global()
def cat_icon(category_name):
    """Return ThreadVerse SVG category icon (same style as icon_data.py set)."""
    name = (category_name or "").strip().lower()
    mapping = {
        "dress": "dress",
        "gown": "dress",
        "shirt": "shirt",
        "top": "shirt",
        "tee": "shirt",
        "t-shirt": "shirt",
        "jean": "pants",
        "pant": "pants",
        "trouser": "pants",
        "jogger": "pants",
        "coat": "coat",
        "jacket": "coat",
        "hoodie": "coat",
        "outerwear": "coat",
        "bag": "bag",
    }
    icon_name = "sparkle"
    for key, value in mapping.items():
        if key in name:
            icon_name = value
            break
    return icon(icon_name, size=22, cls='cat-svg')

# ── SESSION HELPERS ───────────────────────────────────────────────────────────

def get_sid():
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    return session['session_id']

def current_user():
    uid = session.get('user_id')
    if not uid:
        return None
    return db.get_user_by_id(uid)

def active_mode():
    """Returns 'vendor' or 'customer' based on current session mode."""
    return session.get('active_mode', 'customer')

def is_style_house(shop_name):
    return (shop_name or '').strip().lower() == 'style house'

def clean_item(item):
    return {k: v for k, v in item.items() if k != 'session_id'}

# Demo account IDs — these are strictly locked to their role
DEMO_CUSTOMER_IDS = {'u001'}   # customer@demo.com — can ONLY shop
DEMO_VENDOR_IDS   = {'v001'}   # vendor@demo.com  — can ONLY sell

def is_demo_customer(uid):
    return uid in DEMO_CUSTOMER_IDS

def is_demo_vendor(uid):
    return uid in DEMO_VENDOR_IDS

# ── AUTH DECORATORS ───────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return decorated

def vendor_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = current_user()
        if not user:
            return redirect(url_for('login', next=request.path))
        uid = user['id']
        # Demo customer account can NEVER sell
        if is_demo_customer(uid):
            flash('This demo account is for shopping only.', 'warning')
            return redirect(url_for('home'))
        # Any other user can sell IF they have a shop set up
        if not user.get('shop_name'):
            return redirect(url_for('setup_vendor'))
        session['active_mode'] = 'vendor'
        return f(*args, **kwargs)
    return decorated

def customer_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = current_user()
        if not user:
            return redirect(url_for('login', next=request.path))
        uid = user['id']
        # Demo vendor account can NEVER shop
        if is_demo_vendor(uid):
            flash('This demo account is for selling only.', 'warning')
            return redirect(url_for('vendor_dashboard'))
        return f(*args, **kwargs)
    return decorated

# ── AUTH PAGES ────────────────────────────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    # Allow explicit re-login flow (used by "Become a Vendor" CTA).
    if request.args.get('force') == '1' and session.get('user_id'):
        session.clear()

    if session.get('user_id'):
        if active_mode() == 'vendor':
            return redirect(url_for('vendor_dashboard'))
        return redirect(url_for('home'))

    form  = LoginForm()
    error = None

    if form.validate_on_submit():
        email         = form.email.data.strip().lower()
        password      = form.password.data.strip()
        selected_role = form.selected_role.data or request.form.get('selected_role', '')
        preferred_store = form.preferred_store.data or request.form.get('preferred_store', '')

        user = db.get_user_by_email(email)
        if user and db.verify_password(password, user['password']):
            session['user_id']   = user['id']
            session['user_name'] = user['name']
            session['user_role'] = user['role']
            if selected_role == 'vendor':
                if not user.get('shop_name'):
                    session['active_mode'] = 'customer'
                    return redirect(url_for('setup_vendor'))
                session['active_mode'] = 'vendor'
                return redirect(url_for('vendor_dashboard'))
            else:
                session['active_mode'] = 'customer'
                if preferred_store:
                    session['preferred_store'] = preferred_store
                next_page = form.next.data or request.args.get('next', '')
                return redirect(next_page if next_page else url_for('stores_page', from_login='1'))
        else:
            error = 'Invalid email or password. Please try again.'

    # Fetch store list for the store selector dropdown
    stores = db.query("""
        SELECT u.id, u.name, u.shop_name
        FROM users u
        WHERE u.role = 'vendor' AND u.shop_name IS NOT NULL AND u.shop_name <> ''
        ORDER BY u.shop_name ASC
    """)

    return render_template('login.html', form=form, error=error,
                           next=request.args.get('next', ''), stores=stores)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if session.get('user_id'):
        return redirect(url_for('home'))

    form  = RegisterForm()
    error = None

    if form.validate_on_submit():
        name      = form.name.data.strip()
        email     = form.email.data.strip().lower()
        password  = form.password.data.strip()
        role      = form.role.data
        shop_name = (form.shop_name.data or '').strip()
        contact   = form.contact_number.data.strip()
        otp_input = (form.otp.data or '').strip()

        # OTP verification skipped — no OTP flow
        if len(password) < 6:
            error = 'Password must be at least 6 characters.'
        elif db.get_user_by_email(email):
            error = 'An account with this email already exists.'
        else:
            # Handle verification document upload (vendors only)
            doc_path = None
            if role == 'vendor' and form.verification_doc.data and form.verification_doc.data.filename:
                f = form.verification_doc.data
                filename = secure_filename(f.filename)
                ext = filename.rsplit('.', 1)[-1].lower()
                if ext in ALLOWED_DOC_EXTENSIONS:
                    unique_name = f"{uuid.uuid4().hex}.{ext}"
                    f.save(os.path.join(UPLOAD_FOLDER, unique_name))
                    doc_path = f"uploads/verification/{unique_name}"
                else:
                    error = 'Invalid document format. Use PDF, JPG, or PNG.'

            if not error:
                uid = ('v' if role == 'vendor' else 'u') + str(uuid.uuid4())[:6]
                created = datetime.now().strftime('%d %b %Y')
                db.create_user(uid, name, email, password, role, shop_name or '', created,
                               contact_number=contact, verification_doc=doc_path)
                session['user_id']   = uid
                session['user_name'] = name
                session['user_role'] = role
                if role == 'vendor':
                    session['active_mode'] = 'vendor'
                    return redirect(url_for('vendor_dashboard'))
                session['active_mode'] = 'customer'
                return redirect(url_for('home'))

    return render_template('register.html', form=form, error=error)


# ── OTP ENDPOINT ──────────────────────────────────────────────────────────────

@app.route('/api/send-otp', methods=['POST'])
@csrf.exempt
def send_otp():
    """Generate and (simulate) send OTP to the given phone number."""
    data  = request.get_json() or {}
    phone = (data.get('phone') or '').strip()
    if not re.match(r'^\+?[0-9]{10,15}$', phone):
        return jsonify({'success': False, 'error': 'Invalid phone number.'}), 400

    otp = str(random.randint(100000, 999999))
    session['reg_otp']       = otp
    session['reg_otp_phone'] = phone

    # In production: integrate Twilio / MSG91 / Fast2SMS here to SMS the OTP.
    # For development/demo we return the OTP directly so it can be shown.
    return jsonify({'success': True, 'otp': otp,
                    'message': f'OTP sent to {phone} (demo: {otp})'})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ── VENDOR SETUP (for customers switching to vendor mode) ─────────────────────

@app.route('/setup-vendor', methods=['GET', 'POST'])
@login_required
def setup_vendor():
    user  = current_user()
    error = None
    if request.method == 'POST':
        shop_name = request.form.get('shop_name', '').strip()
        if not shop_name:
            error = 'Shop name is required.'
        else:
            db.execute("UPDATE users SET shop_name=%s WHERE id=%s", (shop_name, user['id']))
            session['active_mode'] = 'vendor'
            return redirect(url_for('vendor_dashboard'))
    return render_template('setup_vendor.html', user=user, error=error)

# ── MODE SWITCH ───────────────────────────────────────────────────────────────

@app.route('/switch-mode')
@login_required
def switch_mode():
    user = current_user()
    uid = user['id']
    current = active_mode()
    if current == 'vendor':
        # Demo vendor can never switch to customer/shopping mode
        if is_demo_vendor(uid):
            flash('This demo account is for selling only.', 'warning')
            return redirect(url_for('vendor_dashboard'))
        session['active_mode'] = 'customer'
        return redirect(url_for('home'))
    else:
        # Demo customer can never switch to vendor/selling mode
        if is_demo_customer(uid):
            flash('This demo account is for shopping only.', 'warning')
            return redirect(url_for('home'))
        # Switch to vendor — check if shop is set up
        if not user.get('shop_name'):
            return redirect(url_for('setup_vendor'))
        session['active_mode'] = 'vendor'
        return redirect(url_for('vendor_dashboard'))

# ── CUSTOMER PAGES ────────────────────────────────────────────────────────────

@app.route('/')
@login_required
@customer_required
def home():
    products   = db.get_products()
    featured   = products[:12]
    hero_products = products[:4] if len(products) >= 4 else products
    categories = sorted({p['category'] for p in products})
    user       = current_user()
    return render_template(
        'home.html',
        featured=featured,
        hero_products=hero_products,
        categories=categories,
        user=user
    )

@app.route('/shop')
@login_required
@customer_required
def shop():
    filters = {
        'q': request.args.get('q', '').strip(),
        'category': request.args.get('category', '').strip(),
        'gender': request.args.get('gender', '').strip(),
        'sort': request.args.get('sort', '').strip(),
        'min_price': request.args.get('min_price', '').strip(),
        'max_price': request.args.get('max_price', '').strip(),
    }

    max_price = None
    try:
        if filters['max_price']:
            max_price = float(filters['max_price'])
    except ValueError:
        max_price = None

    products = db.get_products(
        category=filters['category'] or None,
        gender=filters['gender'] or None,
        search=filters['q'] or None,
        max_price=max_price,
        sort=filters['sort'] or 'default'
    )

    # Apply min price in app layer (db helper currently supports max_price only).
    try:
        if filters['min_price']:
            min_price = float(filters['min_price'])
            products = [p for p in products if float(p.get('price') or 0) >= min_price]
    except ValueError:
        pass

    categories = sorted({p['category'] for p in db.get_products()})
    user = current_user()
    return render_template(
        'shop.html',
        products=products,
        categories=categories,
        filters=filters,
        total=len(products),
        user=user
    )

@app.route('/chat')
@login_required
@customer_required
def chat():
    user = current_user()
    return render_template('chat.html', user=user)

@app.route('/product/<int:product_id>')
@login_required
@customer_required
def product_detail(product_id):
    product = db.get_product(product_id)
    if not product:
        return "Product not found", 404
    related = [p for p in db.get_products(category=product['category']) if p['id'] != product_id][:4]
    user = current_user()
    return render_template('product.html', product=product, related=related, user=user)

@app.route('/cart')
@login_required
@customer_required
def cart_page():
    cart  = db.get_cart(get_sid())
    total = sum(item['price'] * item.get('qty', 1) for item in cart)
    user  = current_user()
    return render_template('cart.html', cart=cart, total=round(total, 2), user=user)

@app.route('/checkout', methods=['GET', 'POST'])
@login_required
@customer_required
def checkout_page():
    cart = db.get_cart(get_sid())
    if not cart:
        return redirect(url_for('cart_page'))

    user = current_user()
    total = round(sum(item['price'] * item.get('qty', 1) for item in cart), 2)

    # Template expects item.size, while DB uses selected_size.
    checkout_items = [{**item, 'size': item.get('selected_size', '')} for item in cart]

    if request.method == 'POST':
        shipping = {
            'name': request.form.get('name', '').strip(),
            'address': request.form.get('address', '').strip(),
            'city': request.form.get('city', '').strip(),
        }
        order_id = f"ORD-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
        db.create_order(
            order_id=order_id,
            user_id=session.get('user_id'),
            items=cart,
            total=total,
            status='Confirmed',
            date=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            shipping=shipping
        )
        db.cart_clear(get_sid())
        return redirect(url_for('orders_page'))

    return render_template('checkout.html', cart=checkout_items, total=total, user=user)

@app.route('/stores')
def stores_page():
    vendors = db.query("""
        SELECT
            u.id,
            u.name,
            u.shop_name,
            (SELECT COUNT(*) FROM products p WHERE p.vendor_id = u.id) AS product_count
        FROM users u
        WHERE u.role = 'vendor' AND u.shop_name IS NOT NULL AND u.shop_name <> ''
        ORDER BY u.shop_name ASC
    """)
    user = current_user()
    return render_template(
        'stores.html',
        vendors=vendors,
        user=user,
        from_login=request.args.get('from_login') == '1'
    )

@app.route('/store/<store_ref>')
def store_page(store_ref):
    # Try matching by vendor ID (string or numeric)
    vendor = db.query_one(
        "SELECT id, name, shop_name FROM users WHERE id=%s AND role='vendor'",
        (store_ref,)
    )
    if not vendor:
        vendor = db.query_one(
            "SELECT id, name, shop_name FROM users WHERE shop_name=%s AND role='vendor'",
            (store_ref,)
        )
    if not vendor:
        return "Store not found", 404

    q = request.args.get('q', '').strip()
    category = request.args.get('category', '').strip() or None
    sort = request.args.get('sort', 'default').strip() or 'default'
    products = db.get_products(category=category, search=q or None, sort=sort, vendor_id=vendor['id'])
    categories = sorted({p['category'] for p in db.get_products(vendor_id=vendor['id'])})
    user = current_user()
    filters = {'q': q, 'category': category or '', 'sort': sort}
    return render_template(
        'store.html',
        vendor=vendor,
        products=products,
        categories=categories,
        total=len(products),
        filters=filters,
        user=user
    )

@app.route('/wishlist')
@login_required
@customer_required
def wishlist_page():
    wl   = db.get_wishlist(get_sid())
    user = current_user()
    return render_template('wishlist.html', wishlist=wl, user=user)

@app.route('/orders')
@login_required
@customer_required
def orders_page():
    my_orders = db.get_orders_for_user(session.get('user_id'))
    user      = current_user()
    return render_template('orders.html', orders=my_orders, user=user)

@app.route('/about')
def about():
    user = current_user()
    return render_template('about.html', user=user)

@app.route('/contact')
def contact():
    user = current_user()
    return render_template('contact.html', user=user)

# ── VENDOR PAGES ──────────────────────────────────────────────────────────────

@app.route('/vendor')
@vendor_required
def vendor_dashboard():
    user = current_user()
    products                                     = db.get_products(vendor_id=user['id'])
    total_products, total_orders, total_revenue  = db.get_vendor_stats(user['id'])
    return render_template('vendor/dashboard.html',
        user=user, products=products,
        total_products=total_products,
        total_orders=total_orders,
        total_revenue=total_revenue
    )

@app.route('/vendor/products')
@vendor_required
def vendor_products():
    user     = current_user()
    products = db.get_products(vendor_id=user['id'])
    return render_template('vendor/products.html', user=user, products=products)

@app.route('/vendor/add-product', methods=['GET', 'POST'])
@vendor_required
def vendor_add_product():
    user  = current_user()
    error = None
    if request.method == 'POST':
        sizes_raw = request.form.get('sizes', 'S,M,L,XL')
        tags_raw  = request.form.get('tags', '')
        image_url = request.form.get('image_url', '').strip()
        try:
            price = float(request.form.get('price', 0))
            stock = int(request.form.get('stock', 0))
        except ValueError:
            error = 'Price and stock must be valid numbers.'
            return render_template('vendor/add_product.html', user=user, error=error)

        name = request.form.get('name', '').strip()
        if not name:
            error = 'Product name is required.'
            return render_template('vendor/add_product.html', user=user, error=error)

        db.execute(
            """INSERT INTO products
               (name,category,subcategory,gender,color,sizes,price,occasion,tags,
                rating,reviews,stock,image,description,vendor_id,vendor_name)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,0,0,%s,%s,%s,%s,%s)""",
            (name,
             request.form.get('category','').strip().lower(),
             request.form.get('subcategory','').strip().lower(),
             request.form.get('gender','unisex'),
             request.form.get('color','').strip().lower(),
             ','.join(s.strip() for s in sizes_raw.split(',') if s.strip()),
             price,
             request.form.get('occasion','').strip().lower(),
             ','.join(t.strip() for t in tags_raw.split(',') if t.strip()),
             stock, image_url,
             request.form.get('description','').strip(),
             user['id'], user.get('shop_name', user['name']))
        )
        return redirect(url_for('vendor_products'))

    return render_template('vendor/add_product.html', user=user, error=error)

@app.route('/vendor/edit-product/<int:product_id>', methods=['GET', 'POST'])
@vendor_required
def vendor_edit_product(product_id):
    user    = current_user()
    product = db.get_product(product_id)
    if not product or product.get('vendor_id') != user['id']:
        return redirect(url_for('vendor_products'))

    error = None
    if request.method == 'POST':
        sizes_raw = request.form.get('sizes', 'S,M,L,XL')
        tags_raw  = request.form.get('tags', '')
        image_url = request.form.get('image_url', '').strip()
        try:
            price = float(request.form.get('price', 0))
            stock = int(request.form.get('stock', 0))
        except ValueError:
            error = 'Price and stock must be valid numbers.'
            return render_template('vendor/edit_product.html', user=user, product=product, error=error)

        db.execute(
            """UPDATE products SET
               name=%s, category=%s, subcategory=%s, gender=%s, color=%s,
               sizes=%s, price=%s, occasion=%s, tags=%s, stock=%s,
               image=%s, description=%s
               WHERE id=%s AND vendor_id=%s""",
            (request.form.get('name','').strip(),
             request.form.get('category','').strip().lower(),
             request.form.get('subcategory','').strip().lower(),
             request.form.get('gender','unisex'),
             request.form.get('color','').strip().lower(),
             ','.join(s.strip() for s in sizes_raw.split(',') if s.strip()),
             price,
             request.form.get('occasion','').strip().lower(),
             ','.join(t.strip() for t in tags_raw.split(',') if t.strip()),
             stock, image_url or product.get('image',''),
             request.form.get('description','').strip(),
             product_id, user['id'])
        )
        return redirect(url_for('vendor_products'))

    return render_template('vendor/edit_product.html', user=user, product=product, error=error)

@app.route('/vendor/delete-product/<int:product_id>', methods=['POST'])
@vendor_required
def vendor_delete_product(product_id):
    user = current_user()
    product = db.query_one("SELECT id FROM products WHERE id=%s AND vendor_id=%s", (product_id, user['id']))
    if not product:
        flash('You can only delete products from your own store.', 'warning')
        return redirect(url_for('vendor_products'))

    # Remove FK-constrained rows only after ownership is validated
    db.execute("DELETE FROM cart WHERE product_id=%s", (product_id,))
    db.execute("DELETE FROM wishlist WHERE product_id=%s", (product_id,))
    db.execute("DELETE FROM order_items WHERE product_id=%s", (product_id,))
    db.execute("DELETE FROM products WHERE id=%s AND vendor_id=%s", (product_id, user['id']))
    flash('Product deleted.', 'success')
    return redirect(url_for('vendor_products'))

@app.route('/vendor/orders')
@vendor_required
def vendor_orders():
    user      = current_user()
    my_orders = db.get_orders_for_vendor(user['id'])
    return render_template('vendor/orders.html', user=user, orders=my_orders)

@app.route('/vendor/profile', methods=['GET', 'POST'])
@vendor_required
def vendor_profile():
    user    = current_user()
    error   = None
    success = None
    if request.method == 'POST':
        new_name  = request.form.get('name', user['name']).strip()
        new_shop  = request.form.get('shop_name', user.get('shop_name','')).strip()
        new_pass  = request.form.get('new_password', '').strip()
        if new_pass and len(new_pass) < 6:
            error = 'Password must be at least 6 characters.'
        else:
            if new_pass:
                db.execute("UPDATE users SET name=%s, shop_name=%s, password=%s WHERE id=%s",
                           (new_name, new_shop, db.hash_password(new_pass), user['id']))
            else:
                db.execute("UPDATE users SET name=%s, shop_name=%s WHERE id=%s",
                           (new_name, new_shop, user['id']))
            session['user_name'] = new_name
            success = 'Profile updated successfully!'
            user = current_user()
    return render_template('vendor/profile.html', user=user, error=error, success=success)

# ── CUSTOMER API ──────────────────────────────────────────────────────────────

@app.route('/api/products')
def api_products():
    category  = request.args.get('category', '').strip()
    gender    = request.args.get('gender', '').strip()
    search    = request.args.get('search', '').lower().strip()
    max_price = request.args.get('max_price', type=float)
    sort      = request.args.get('sort', 'default')
    products  = db.get_products(
        category=category or None,
        gender=gender or None,
        search=search or None,
        max_price=max_price,
        sort=sort
    )
    return jsonify(products)

@app.route('/api/cart', methods=['GET'])
def api_cart_get():
    return jsonify(db.get_cart(get_sid()))

@app.route('/api/cart/add', methods=['POST'])
@csrf.exempt
def api_cart_add():
    sid     = get_sid()
    data    = request.json or {}
    pid     = data.get('id')
    product = db.get_product(pid)
    if not product:
        return jsonify({'error': 'Not found'}), 404
    size    = data.get('size') or (product['sizes'][0] if product.get('sizes') else 'M')
    db.cart_add(sid, product, size)
    count = len(db.get_cart(sid))
    return jsonify({'success': True, 'count': count})

@app.route('/api/cart/remove', methods=['POST'])
@csrf.exempt
def api_cart_remove():
    sid = get_sid()
    pid = (request.json or {}).get('id')
    db.cart_remove(sid, pid)
    return jsonify({'success': True})

@app.route('/api/cart/update', methods=['POST'])
@csrf.exempt
def api_cart_update():
    sid  = get_sid()
    data = request.json or {}
    pid  = data.get('id')
    qty  = data.get('qty', 1)
    db.cart_update(sid, pid, qty)
    cart  = db.get_cart(sid)
    total = sum(i['price'] * i.get('qty',1) for i in cart)
    return jsonify({'success': True, 'count': len(cart), 'total': round(total,2)})

@app.route('/api/cart/checkout', methods=['POST'])
@csrf.exempt
def api_cart_checkout():
    sid  = get_sid()
    cart = db.get_cart(sid)
    if not cart:
        return jsonify({'error': 'Cart is empty'}), 400
    uid = session.get('user_id')
    if not uid:
        return jsonify({'error': 'Not logged in'}), 401
    data     = request.json or {}
    shipping = data.get('shipping', {})
    total    = sum(i['price'] * i.get('qty', 1) for i in cart)
    order_id = str(uuid.uuid4())[:8].upper()
    for item in cart:
        if 'id' not in item or item['id'] != item.get('product_id'):
            item['id'] = item.get('product_id')
    db.create_order(
        order_id,
        uid,
        cart, total, 'Confirmed',
        datetime.now().strftime('%d %b %Y, %H:%M'),
        shipping
    )
    db.cart_clear(sid)
    return jsonify({'success': True, 'order_id': order_id})

@app.route('/api/cart/clear', methods=['POST'])
@csrf.exempt
def api_cart_clear():
    db.cart_clear(get_sid())
    return jsonify({'success': True})

@app.route('/api/wishlist/toggle', methods=['POST'])
@csrf.exempt
def api_wishlist_toggle():
    sid     = get_sid()
    pid     = (request.json or {}).get('id')
    product = db.get_product(pid)
    if not product:
        return jsonify({'error': 'Not found'}), 404
    added = db.wishlist_toggle(sid, product)
    return jsonify({'success': True, 'added': added, 'count': len(db.get_wishlist(sid))})

@app.route('/api/wishlist/remove', methods=['POST'])
@csrf.exempt
def api_wishlist_remove():
    sid = get_sid()
    pid = (request.json or {}).get('id')
    db.execute("DELETE FROM wishlist WHERE session_id=%s AND product_id=%s", (sid, pid))
    return jsonify({'success': True})

@app.route('/api/cart/count')
def api_cart_count():
    return jsonify({'count': len(db.get_cart(get_sid()))})

# ── RAG CHATBOT ───────────────────────────────────────────────────────────────

_COLOR_ALIASES = {
    "red"       : ["red","burgundy","rust","terracotta"],
    "blue"      : ["blue","navy","cobalt","indigo","sky blue","powder blue","royal blue","dark indigo"],
    "navy"      : ["navy","dark indigo"],
    "black"     : ["black"],
    "white"     : ["white","cream","ivory","pearl"],
    "green"     : ["green","olive","sage","forest","emerald","sage green","forest green"],
    "grey"      : ["grey","gray","charcoal"],
    "gray"      : ["grey","gray","charcoal"],
    "brown"     : ["brown","tan","camel","chocolate","dark brown"],
    "pink"      : ["pink","blush","dusty rose"],
    "yellow"    : ["yellow"],
    "orange"    : ["orange","terracotta","rust"],
    "purple"    : ["purple","lavender","burgundy"],
    "lavender"  : ["lavender"],
    "beige"     : ["beige","tan","camel","cream","oatmeal"],
    "cream"     : ["cream","ivory","oatmeal"],
    "khaki"     : ["khaki","tan","beige"],
    "maroon"    : ["burgundy","maroon"],
    "burgundy"  : ["burgundy"],
    "olive"     : ["olive","sage","khaki"],
    "gold"      : ["gold","camel","champagne"],
    "cobalt"    : ["cobalt","cobalt blue","royal blue"],
    "indigo"    : ["indigo","dark indigo"],
    "camel"     : ["camel","tan","beige"],
    "sage"      : ["sage","sage green"],
    "blush"     : ["blush","dusty rose","pink"],
    "dusty pink": ["dusty rose","blush","pink"],
    "rose"      : ["dusty rose","blush","pink"],
    "terracotta": ["terracotta"],
    "multicolor": ["multicolor"],
    "peach"     : ["peach","blush"],
    "forest"    : ["forest green"],
}
_RAG_COLORS = list(_COLOR_ALIASES.keys())

_OCCASION_TAGS = {
    "office"    : ["office","formal","workwear","smart","business"],
    "work"      : ["office","formal","workwear","smart","business"],
    "formal"    : ["formal","suit","office","smart"],
    "party"     : ["party","night out","cocktail","festive","sequin","satin"],
    "casual"    : ["casual","everyday","relaxed","basic","minimal"],
    "summer"    : ["summer","beach","tropical","floral","linen"],
    "winter"    : ["winter","wool","warm","cozy","puffer","parka","shearling"],
    "gym"       : ["gym","activewear","sport","athletic"],
    "sport"     : ["sport","athletic","gym","activewear"],
    "wedding"   : ["formal","elegant","suit","festive"],
    "date"      : ["night out","party","elegant"],
    "beach"     : ["beach","summer","tropical","floral"],
    "floral"    : ["floral","botanical","print"],
    "night out" : ["party","night out","sequin","satin","festive"],
}

_RAG_CATS = [
    "dress","shirt","jacket","pant","jean","skirt","top","blouse",
    "coat","sweater","hoodie","knitwear","short","activewear",
    "jumpsuit","set","outerwear","blazer",
    "tote","clutch","crossbody","handbag","purse","satchel",
    "bag","necklace","earring","scarf","sunglass","accessory",
]
_CAT_MAP = {
    "dress":"dresses","shirt":"shirts","jacket":"jackets","pant":"pants",
    "jean":"jeans","skirt":"skirts","top":"tops","blouse":"tops","coat":"coats",
    "sweater":"knitwear","hoodie":"hoodies","knitwear":"knitwear","short":"shorts",
    "activewear":"activewear","jumpsuit":"jumpsuits","set":"sets",
    "outerwear":"outerwear","blazer":"blazers",
    "tote":"bags","clutch":"bags","crossbody":"bags","handbag":"bags",
    "purse":"bags","satchel":"bags","bag":"bags",
    "necklace":"accessories","earring":"accessories","scarf":"accessories",
    "sunglass":"accessories","accessory":"accessories",
}
_CAT_DISPLAY = {
    "dresses":"Dresses","shirts":"Shirts","jackets":"Jackets","pants":"Trousers",
    "jeans":"Jeans","skirts":"Skirts","tops":"Tops","coats":"Coats",
    "knitwear":"Knitwear","hoodies":"Hoodies","shorts":"Shorts",
    "blazers":"Blazers","bags":"Bags","accessories":"Accessories",
}
_RESERVED = {"top rated","top picks","top items","top products","short list","set a budget"}


def _rag_filter(query):
    q = query.lower().strip()

    detected_cat_key = None
    if not any(phrase in q for phrase in _RESERVED):
        detected_cat_key = next(
            (c for c in _RAG_CATS if re.search(r'\b' + re.escape(c) + r'(?:es|s)?\b', q)), None
        )
    detected_cat_db = _CAT_MAP.get(detected_cat_key)

    gender = None
    if re.search(r"\bwomen'?s?\b|\bfemale\b|\bladies\b|\bgirl\b", q): gender = "women"
    elif re.search(r"\bmen'?s?\b|\bmale\b|\bguys\b|\bboy\b", q):      gender = "men"

    if re.search(r'\b(top rated|best rated|highest rated|best seller|most popular|trending)\b', q):
        all_p = db.get_products(category=detected_cat_db, gender=gender, sort='rating')
        return all_p[:8], detected_cat_db, None, gender

    if re.search(r'\b(new arrivals?|latest|newest|just in|just arrived|new in)\b', q):
        all_p = db.get_products(category=detected_cat_db, gender=gender)
        return sorted(all_p, key=lambda x: x.get('id', 0), reverse=True)[:8], detected_cat_db, None, gender

    if re.search(r'\b(show all products?|all products?|everything|browse all)\b', q):
        all_p = db.get_products()
        random.shuffle(all_p)
        return all_p[:8], None, None, None

    price_max = price_min = None
    m = re.search(r'(?:under|below|less than|max|up to)\s*₹?\s*(\d+)', q)
    if m: price_max = float(m.group(1))
    m = re.search(r'(?:above|over|more than|at least|min)\s*₹?\s*(\d+)', q)
    if m: price_min = float(m.group(1))

    detected_color_key = None
    for c in _RAG_COLORS:
        if re.search(r'(?<![a-z])' + re.escape(c) + r'(?![a-z])', q):
            detected_color_key = c; break
    color_substrings = _COLOR_ALIASES.get(detected_color_key, [])

    occasion_tags = []
    for kw, tags in _OCCASION_TAGS.items():
        if re.search(r'\b' + re.escape(kw) + r'\b', q):
            occasion_tags.extend(tags)
    occasion_tags = list(set(occasion_tags))

    all_p = db.get_products(
        category=detected_cat_db,
        gender=gender,
        max_price=price_max
    )

    results = []
    for p in all_p:
        pcolor    = p.get("color", "").lower()
        ptags     = [t.lower() for t in p.get("tags", [])]
        poccasion = p.get("occasion", "").lower()

        if price_min is not None and float(p['price']) < price_min:
            continue
        if color_substrings and not any(cs in pcolor for cs in color_substrings):
            continue
        if occasion_tags:
            tag_match    = any(ot in ptags     for ot in occasion_tags)
            occ_match    = any(ot in poccasion for ot in occasion_tags)
            if not tag_match and not occ_match:
                continue
        results.append(p)

    return results, detected_cat_db, detected_color_key, gender


def _rag_prompt(query, filtered, history=None):
    if filtered:
        sorted_f = sorted(filtered, key=lambda x: x.get("rating",0), reverse=True)
        lines    = [f"- {p['name']} | ₹{int(p['price'])} | {p.get('color','')} | Rating:{p.get('rating','N/A')}"
                    for p in sorted_f[:8]]
        catalogue = "\n".join(lines)
        count = len(filtered)
    else:
        catalogue = "No matching products found."
        count = 0

    hist_text = ""
    if history:
        parts = [("Customer" if t.get("role")=="user" else "Assistant") + ": " + t.get("content","")
                 for t in history[-4:]]
        hist_text = "\n".join(parts) + "\n\n"

    return f"""You are ThreadVerse AI, a concise fashion assistant for ThreadVerse online store.

STRICT RULES:
- Write ONLY 1 short sentence (max 15 words) as an intro to the product cards.
- NEVER name or describe a specific product — the cards already show them.
- Just write a warm general intro like: "Here are some great options for you!"
- If no products found, say so honestly in 1 sentence.
- For greetings, respond warmly without mentioning products.

{hist_text}Matching products ({count} found):
{catalogue}

Customer: {query}

Reply (1 sentence intro only, do NOT name specific products):"""


def _rag_suggestions(cat, color, gender, no_results=False):
    cat_label = _CAT_DISPLAY.get(cat, cat.capitalize()) if cat else None
    sugs = []
    if no_results and cat_label:
        sugs = [f"Yes, show all {cat_label}", "Show all products", "Under ₹2,999", "Top rated"]
    else:
        if cat_label: sugs.append(f"Show all {cat_label}")
        if color:     sugs.append(f"More {color} items")
        if gender == "women": sugs += ["Show dresses", "Women's tops"]
        elif gender == "men": sugs += ["Men's jackets", "Show shirts"]
        sugs += ["Under ₹2,999", "Top rated", "New arrivals", "Show all products"]
    seen, out = set(), []
    for s in sugs:
        if s.lower() not in seen:
            seen.add(s.lower()); out.append(s)
    return out[:5]


@app.route('/api/chat', methods=['POST'])
@csrf.exempt
def api_chat():
    data     = request.json or {}
    user_msg = data.get('message','').strip()
    history  = data.get('history', [])
    if not user_msg:
        return jsonify({'type':'text','message':'Please type something!','suggestions':[]})

    filtered, cat, color, gender = _rag_filter(user_msg)

    try:
        prompt   = _rag_prompt(user_msg, filtered, history)
        response = _groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role":"user","content":prompt}],
            max_tokens=300
        )
        bot_text = response.choices[0].message.content.strip()
    except Exception as e:
        import traceback; traceback.print_exc()
        err = str(e).lower()
        if "api_key" in err or "authentication" in err or "unauthorized" in err:
            bot_text = "❌ Invalid API key — check app.py line 8."
        elif "rate" in err or "limit" in err:
            bot_text = "⏳ Rate limit reached — please wait a moment."
        elif "connect" in err or "network" in err or "timeout" in err:
            bot_text = "❌ Network error — check your connection."
        else:
            bot_text = f"❌ Error: {e}"
        filtered = []

    greeting_words = ["hi","hello","hey","good morning","good afternoon","thanks","thank you"]
    is_greeting    = any(w in user_msg.lower() for w in greeting_words)
    no_results     = not filtered and not is_greeting
    products_to_show = sorted(filtered, key=lambda x: x.get('rating',0), reverse=True)[:8] if filtered else []

    if no_results:
        cat_label = _CAT_DISPLAY.get(cat, cat.capitalize()) if cat else None
        bot_text = (
            f"🔍 Couldn't find an exact match. Explore our full <strong>{cat_label}</strong> collection?"
            if cat_label else
            "🔍 Couldn't find an exact match. Try a different category or colour?"
        )
        products_to_show = []

    suggestions = _rag_suggestions(cat, color, gender, no_results=no_results)
    return jsonify({
        'type':     'products' if products_to_show else 'text',
        'message':  bot_text,
        'products': products_to_show,
        'suggestions': suggestions,
    })


# ── PAYMENT GATEWAY ───────────────────────────────────────────────────────────

def _generate_upi_qr(amount: float, ref: str = '') -> str:
    """Return a base64-encoded PNG of a UPI payment QR code."""
    upi_url = (
        f"upi://pay?pa=threadverse@upi"
        f"&pn=ThreadVerse"
        f"&am={amount:.2f}"
        f"&cu=INR"
        f"&tn=ThreadVerse+Order+{ref}"
    )
    qr = qrcode.QRCode(version=1, box_size=8, border=4,
                       error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(upi_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#111111", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return base64.b64encode(buf.getvalue()).decode('utf-8')


@app.route('/api/payment/qr')
@login_required
def api_payment_qr():
    """Return a base64 UPI QR code for the current cart total."""
    cart   = db.get_cart(get_sid())
    total  = round(sum(i['price'] * i.get('qty', 1) for i in cart), 2)
    ref    = request.args.get('ref', str(uuid.uuid4())[:8].upper())
    qr_b64 = _generate_upi_qr(total, ref)
    return jsonify({'success': True, 'qr': qr_b64, 'amount': total, 'ref': ref,
                    'upi_id': 'threadverse@upi'})


@app.route('/api/payment/verify', methods=['POST'])
@login_required
@csrf.exempt
def api_payment_verify():
    """
    Simulate payment verification.
    In production: call your payment provider's verify API here.
    """
    data = request.get_json() or {}
    method = data.get('method', '')      # 'qr' | 'upi' | 'bank'
    ref    = data.get('ref', '')
    # Placeholder: always returns success in demo mode
    return jsonify({'success': True, 'verified': True,
                    'method': method, 'ref': ref,
                    'message': 'Payment verified (demo mode).'})


# ── ADMIN: one-time vendor cleanup ───────────────────────────────────────────

@app.route('/admin/cleanup-vendors', methods=['POST'])
@login_required
def admin_cleanup_vendors():
    flash('Store deletion is disabled.', 'warning')
    return redirect(url_for('vendor_dashboard'))


# ── CONTEXT PROCESSOR ─────────────────────────────────────────────────────────

@app.context_processor
def inject_utils():
    def product_image_url(product_id, item=None):
        if item and item.get('image'):
            return item['image']
        p = db.get_product(product_id)
        if p and p.get('image'):
            return p['image']
        return 'https://images.unsplash.com/photo-1441986300917-64674bd600d8?w=400&auto=format&fit=crop&q=60'
    uid = session.get('user_id', '')
    return dict(
        product_image_url=product_image_url,
        active_mode=active_mode(),
        is_demo_customer_user=(uid in DEMO_CUSTOMER_IDS),
        is_demo_vendor_user=(uid in DEMO_VENDOR_IDS),
    )


# ── GOOGLE OAUTH ROUTES ───────────────────────────────────────────────────────

@app.route('/login/google')
def login_google():
    """Redirect user to Google's OAuth consent screen."""
    redirect_uri = url_for('google_callback', _external=True)
    return google.authorize_redirect(redirect_uri)


@app.route('/login/google/callback')
def google_callback():
    """Handle Google's redirect back after consent."""
    try:
        token = google.authorize_access_token()
    except Exception:
        flash('Google sign-in was cancelled or failed. Please try again.', 'warning')
        return redirect(url_for('login'))

    user_info = token.get('userinfo') or google.userinfo()
    google_id  = user_info.get('sub', '')
    email      = (user_info.get('email') or '').lower().strip()
    name       = user_info.get('name') or email.split('@')[0]

    if not google_id or not email:
        flash('Could not retrieve your Google account details. Please try again.', 'warning')
        return redirect(url_for('login'))

    user = db.get_or_create_google_user(google_id, email, name)
    session['user_id']   = user['id']
    session['user_name'] = user['name']
    session['user_role'] = user.get('role', 'customer')
    session['active_mode'] = 'vendor' if user.get('shop_name') else 'customer'

    if user.get('shop_name') and session['active_mode'] == 'vendor':
        return redirect(url_for('vendor_dashboard'))
    return redirect(url_for('home'))


if __name__ == '__main__':
    app.run(debug=True, port=5000)
