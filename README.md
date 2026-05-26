# Threadverse

A multi-vendor fashion commerce platform where small businesses can set up
their own storefront and sell directly to customers — no expensive custom
store needed. Built with Flask, SQLite, and an AI stylist powered by
Llama 3.3 via Groq.

## The Problem

Small clothing vendors don't have the budget or technical knowledge to
build their own online store. Threadverse gives them a ready-made
storefront on a shared platform — they register as a vendor, list their
products, and start selling. Customers get a single place to browse
multiple independent fashion shops.

## Features

**For customers**
- Browse products across all vendor stores, filtered by category, gender,
  colour, and occasion
- AI stylist chat — describe what you're looking for in plain language and
  get product recommendations powered by Llama 3.3 (via Groq)
- Cart, wishlist, checkout with UPI QR code payment
- Order history and tracking

**For vendors**
- Register as a vendor and set up your own storefront
- Add, edit, and delete products with image uploads
- Dashboard to view orders and manage inventory
- Vendor verification via document upload

**Auth**
- Email/password registration with OTP verification
- Google OAuth login
- Role-based sessions — switch between customer and vendor mode

## Stack

- **Backend**: Flask, SQLite (via custom `db.py` layer)
- **AI**: Groq API — Llama 3.3 70B for the stylist chat
- **Auth**: Authlib (Google OAuth), Flask-WTF (CSRF), Werkzeug
- **Frontend**: Jinja2 templates, vanilla JS, custom CSS
- **Other**: qrcode + Pillow for UPI QR generation

## Project structure

```
├── app.py              # All routes and business logic
├── db.py               # SQLite database layer
├── forms.py            # WTForms definitions
├── schema.sql          # DB schema reference (auto-created on first run)
├── icon_data.py        # Inline SVG icon set
├── requirements.txt
├── static/
│   ├── css/            # main.css, fonts.css, chat.css
│   └── js/             # shop.js, cart.js, chat.js, main.js
├── templates/
│   ├── base.html
│   ├── home.html
│   ├── shop.html
│   ├── product.html
│   ├── cart.html
│   ├── checkout.html
│   ├── chat.html
│   ├── stores.html
│   ├── store.html
│   ├── orders.html
│   ├── wishlist.html
│   ├── login.html
│   ├── register.html
│   └── vendor/         # Vendor dashboard templates
└── data/               # Seed data (products, demo users)
```

## Getting started

### Prerequisites

- Python 3.9+
- A [Groq](https://console.groq.com) API key (free tier available)
- A Google OAuth app (optional — only needed for Google login)

### Setup

1. Clone the repository

```bash
git clone https://github.com/your-username/threadverse.git
cd threadverse
```

2. Install dependencies

```bash
pip install -r requirements.txt
```

3. Set environment variables

```bash
export SECRET_KEY=your-secret-key-here
export GROQ_API_KEY=your-groq-api-key-here
export GOOGLE_CLIENT_ID=your-google-client-id        # optional
export GOOGLE_CLIENT_SECRET=your-google-client-secret  # optional
```

4. Run the app

```bash
python app.py
```

The database (`threadverse.db`) is created and seeded automatically on
first run. No manual SQL needed.

5. Demo accounts (seeded automatically)

| Role     | Email               | Password  |
|----------|---------------------|-----------|
| Customer | customer@demo.com   | demo123   |
| Vendor   | vendor@demo.com     | demo123   |

## Notes

- The SQLite database is auto-generated from `data/products.json` on
  first run
- Uploaded vendor verification documents are stored in
  `static/uploads/verification/` — this folder is gitignored
- API keys must be set via environment variables — never hardcoded
