# 🛒 Modern AI-Enhanced E-commerce Cart System

A high-performance, premium e-commerce backend and frontend system featuring intelligent cart operations, automated pricing/discount pipelines, and AI-driven enhancements.

## 🚀 Tech Stack

*   **Python 3**
*   **FastAPI**
*   **Pydantic**
*   **Uvicorn**
*   **Jinja2**
*   **Redis**
*   **HTML5**
*   **CSS3**
*   **Vanilla JavaScript (ES6+)**
*   **localStorage**
*   **Fetch API**
*   **Apriori Algorithm (AI)**
*   **Logistic Regression (AI)**
*   **GBDT (AI)**

## ✨ Core Features

*   **Intelligent Cart Operations**: Full CRUD support for cart items with real-time state synchronization via a robust API.
*   **Automated Pricing Engine**: Real-time calculation of subtotals, tax, shipping, and discounts (including `SAVE10` and `FLAT5` codes).
*   **AI Recommendations (Frequently Bought Together)**: Uses the **Apriori Algorithm** to analyze basket patterns and surface contextually relevant co-purchase suggestions.
*   **AI Upselling (Premium Replacements)**: Intelligently suggests higher-value alternatives from the same category using brand tiering and price guardrails.
*   **AI Price Sensitivity Prediction**: A heuristic model that calculates purchase probability and sensitivity segments (`High`, `Neutral`, `Low`) based on cart composition and discount ratios.
*   **Premium UX/UI**: High-fidelity dark mode interface with glassmorphism, smooth CSS transitions, and an integrated session management system using `localStorage`.
*   **Data Consistency**: Built-in support for **Idempotency Keys** and **Optimistic Concurrency** using version tagging (`X-Cart-Version`).

## 📁 Project Structure

```bash
Ecommerce_cart_system/
├── backend/
│   ├── app/
│   │   ├── ai.py           # AI Engine (Apriori, Upsell, Sensitivity)
│   │   ├── catalog.py      # Product repository
│   │   ├── main.py         # FastAPI Endpoints & Routing
│   │   ├── pricing.py      # Pricing & Discount Logic
│   │   ├── schemas.py      # Pydantic Data Models
│   │   └── storage.py      # Redis/InMemory Cart Persistence
│   └── requirements.txt    # Python Dependencies
├── frontend/
│   ├── static/
│   │   ├── app.js          # Core JS Logic & AI Integration
│   │   └── styles.css      # Premium Design System
│   └── templates/
│       ├── cart.html       # Dynamic Cart Template
│       ├── checkout.html   # Finalization Template
│       └── product_list.html # Catalog Template
└── README.md
```

## 🛠️ Getting Started

### 1. Prerequisites
*   Python 3.10+ installed.
*   (Optional) Redis server for production-grade persistence.

### 2. Installation
Clone the repository and navigate to the backend directory:
```bash
cd Ecommerce_cart_system/backend
pip install -r requirements.txt
```

### 3. Run the Application
Start the FastAPI development server:
```bash
python -m uvicorn app.main:app --reload
```

The application will be available at:
*   **Main Store**: `http://localhost:8000/`
*   **Cart Page**: `http://localhost:8000/cart`
*   **Checkout**: `http://localhost:8000/checkout`
*   **API Docs**: `http://localhost:8000/docs`

## ⚙️ Environment Configuration

| Variable | Description | Default |
| :--- | :--- | :--- |
| `REDIS_URL` | URL for the Redis server. | `None` (Falls back to InMemory) |

## 🧪 Testing AI Features

1.  **Frequently Bought Together**: Add **"Basic T-Shirt"** to your cart; the Apriori model will suggest **"Jeans"** based on historical basket data.
2.  **Upselling**: Add a **"Wireless Mouse"** ($19.99) and refresh the cart; the system will offer a **"Swap to Premium"** button for the **"Gaming Mouse"** ($59.99).
3.  **Price Sensitivity**: Watch your **Purchase Likelihood** score change dynamically as you add items or apply the `SAVE10` discount code.
