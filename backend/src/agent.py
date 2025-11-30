import json
import logging
import os
import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Annotated

from dotenv import load_dotenv
from pydantic import Field
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    RoomInputOptions,
    WorkerOptions,
    cli,
    function_tool,
    RunContext,
)

from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

# -------------------------
# Logging
# -------------------------
logger = logging.getLogger("shopping_agent")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logger.addHandler(handler)

load_dotenv(".env.local")

# -------------------------
# Simple Product Catalog (Lalit's Shop)
# -------------------------
CATALOG: List[Dict] = [
    {
        "id": "mug-001",
        "name": "Stoneware Chai Mug",
        "description": "Hand-glazed ceramic mug perfect for masala chai.",
        "price": 299,
        "currency": "INR",
        "category": "mug",
        "color": "blue",
        "sizes": [],
    },
    {
        "id": "tee-001",
        "name": "Classic Cotton Tee",
        "description": "Comfort-fit cotton t-shirt with subtle logo.",
        "price": 799,
        "currency": "INR",
        "category": "tshirt",
        "color": "black",
        "sizes": ["S", "M", "L", "XL"],
    },
    {
        "id": "hoodie-001",
        "name": "Cozy Hoodie",
        "description": "Warm pullover hoodie, fleece-lined.",
        "price": 1499,
        "currency": "INR",
        "category": "hoodie",
        "color": "grey",
        "sizes": ["M", "L", "XL"],
    },
    {
        "id": "mug-002",
        "name": "Insulated Travel Mug",
        "description": "Keeps chai warm on your way to work.",
        "price": 599,
        "currency": "INR",
        "category": "mug",
        "color": "white",
        "sizes": [],
    },
    {
        "id": "hoodie-002",
        "name": "Black Zip Hoodie",
        "description": "Lightweight zip-up hoodie, black.",
        "price": 1299,
        "currency": "INR",
        "category": "hoodie",
        "color": "black",
        "sizes": ["S", "M", "L"],
    },
    # T-shirts
    {
        "id": "tee-002",
        "name": "Casual Cotton Tee",
        "description": "Everyday cotton t-shirt, breathable and soft.",
        "price": 299,
        "currency": "INR",
        "category": "tshirt",
        "color": "white",
        "sizes": ["S", "M", "L", "XL"],
    },
    {
        "id": "tee-003",
        "name": "Graphic Tee",
        "description": "Printed graphic t-shirt with vibrant design.",
        "price": 499,
        "currency": "INR",
        "category": "tshirt",
        "color": "navy",
        "sizes": ["S", "M", "L", "XL"],
    },
    {
        "id": "tee-004",
        "name": "Premium Polo Tee",
        "description": "Polo-style t-shirt with premium stitching.",
        "price": 999,
        "currency": "INR",
        "category": "tshirt",
        "color": "maroon",
        "sizes": ["M", "L", "XL"],
    },
    {
        "id": "tee-005",
        "name": "Summer V-neck Tee",
        "description": "Lightweight V-neck tee for hot days.",
        "price": 350,
        "currency": "INR",
        "category": "tshirt",
        "color": "sky",
        "sizes": ["S", "M", "L"],
    },
    {
        "id": "tee-006",
        "name": "Henley Tee",
        "description": "Smart casual henley style t-shirt.",
        "price": 699,
        "currency": "INR",
        "category": "tshirt",
        "color": "olive",
        "sizes": ["M", "L", "XL"],
    },
    # Raincoats / Outerwear
    {
        "id": "rain-001",
        "name": "Light Raincoat",
        "description": "Waterproof light raincoat, packable.",
        "price": 1299,
        "currency": "INR",
        "category": "raincoat",
        "color": "yellow",
        "sizes": ["M", "L", "XL"],
    },
    {
        "id": "rain-002",
        "name": "Heavy Duty Raincoat",
        "description": "Heavy-duty rainproof coat for monsoon.",
        "price": 2499,
        "currency": "INR",
        "category": "raincoat",
        "color": "navy",
        "sizes": ["L", "XL"],
    },
    # Laptops
    {
        "id": "laptop-001",
        "name": "Generic Laptop (50k)",
        "description": "A reliable laptop suitable for everyday use.",
        "price": 50000,
        "currency": "INR",
        "category": "laptop",
        "color": "silver",
        "sizes": [],
    },
    {
        "id": "laptop-002",
        "name": "Dell Inspiron (Budget)",
        "description": "Compact Dell laptop for students and professionals.",
        "price": 27800,
        "currency": "INR",
        "category": "laptop",
        "color": "black",
        "sizes": [],
    },
    {
        "id": "laptop-003",
        "name": "Lenovo ThinkPad",
        "description": "Durable Lenovo laptop with strong performance.",
        "price": 60000,
        "currency": "INR",
        "category": "laptop",
        "color": "black",
        "sizes": [],
    },
    {
        "id": "laptop-004",
        "name": "HP Pavilion",
        "description": "High-performance HP laptop for creators.",
        "price": 100000,
        "currency": "INR",
        "category": "laptop",
        "color": "silver",
        "sizes": [],
    },
    # Storage
    {
        "id": "storage-001",
        "name": "External Hard Disk 1TB",
        "description": "Portable external hard disk for backups.",
        "price": 5000,
        "currency": "INR",
        "category": "storage",
        "color": "black",
        "sizes": [],
    },
    # Mobile phones (10k - 50k examples)
    {
        "id": "phone-001",
        "name": "Redmi Note (Entry)",
        "description": "Affordable Redmi smartphone with solid features.",
        "price": 12000,
        "currency": "INR",
        "category": "mobile",
        "color": "blue",
        "sizes": [],
    },
    {
        "id": "phone-002",
        "name": "Oppo A-Series",
        "description": "Stylish Oppo phone with good camera.",
        "price": 18000,
        "currency": "INR",
        "category": "mobile",
        "color": "green",
        "sizes": [],
    },
    {
        "id": "phone-003",
        "name": "Samsung M-Series",
        "description": "Mid-range Samsung phone for everyday use.",
        "price": 25000,
        "currency": "INR",
        "category": "mobile",
        "color": "black",
        "sizes": [],
    },
    {
        "id": "phone-004",
        "name": "iPhone (Standard)",
        "description": "Apple iPhone model example (price varies by config).",
        "price": 50000,
        "currency": "INR",
        "category": "mobile",
        "color": "white",
        "sizes": [],
    },
    {
        "id": "phone-005",
        "name": "Oppo Reno",
        "description": "Higher-end Oppo phone with premium features.",
        "price": 35000,
        "currency": "INR",
        "category": "mobile",
        "color": "black",
        "sizes": [],
    },
    {
        "id": "phone-006",
        "name": "Redmi Pro",
        "description": "Redmi higher-tier phone with improved camera and battery.",
        "price": 22000,
        "currency": "INR",
        "category": "mobile",
        "color": "grey",
        "sizes": [],
    },
]

# -------------------------
# Orders persistence
# -------------------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
ORDERS_FILE = os.path.join(BASE_DIR, "orders.json")

if not os.path.exists(ORDERS_FILE):
    with open(ORDERS_FILE, "w", encoding="utf-8") as f:
        json.dump([], f)


@dataclass
class Userdata:
    customer_name: Optional[str] = None
    session_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    cart: List[Dict] = field(default_factory=list)   # {product_id, quantity, attrs}
    orders: List[Dict] = field(default_factory=list)
    history: List[Dict] = field(default_factory=list)


# -------------------------
# Merchant-layer helpers
# -------------------------
def _load_all_orders() -> List[Dict]:
    try:
        with open(ORDERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_order(order: Dict):
    orders = _load_all_orders()
    orders.append(order)
    with open(ORDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(orders, f, indent=2)


def list_products(filters: Optional[Dict] = None) -> List[Dict]:
    """
    Naive filtering by category, max_price, color, size, and query words.

    - Recognizes category synonyms (phones/mobiles, tees/tshirts).
    - Supports min_price / max_price if present.
    """
    filters = filters or {}
    results: List[Dict] = []

    query = filters.get("q")
    category = filters.get("category")
    max_price = filters.get("max_price") or filters.get("to") or filters.get("max")
    min_price = filters.get("min_price") or filters.get("from") or filters.get("min")
    color = filters.get("color")
    size = filters.get("size")

    # normalize category synonyms
    if category:
        cat = category.lower()
        if cat in ("phone", "phones", "mobile", "mobile phone", "mobiles"):
            category = "mobile"
        elif cat in ("tshirt", "t-shirts", "tees", "tee"):
            category = "tshirt"
        else:
            category = cat

    for p in CATALOG:
        ok = True

        # category matching: allow substring matches
        if category:
            pcat = p.get("category", "").lower()
            if pcat != category and category not in pcat and pcat not in category:
                ok = False

        if max_price:
            try:
                if p.get("price", 0) > int(max_price):
                    ok = False
            except Exception:
                pass

        if min_price:
            try:
                if p.get("price", 0) < int(min_price):
                    ok = False
            except Exception:
                pass

        if color and p.get("color") and p.get("color").lower() != color.lower():
            ok = False

        if size:
            if not p.get("sizes") or size not in p.get("sizes"):
                ok = False

        if query:
            q = query.lower()
            # if query mentions 'phone' or 'mobile', prefer mobile
            if "phone" in q or "mobile" in q:
                if p.get("category") != "mobile":
                    ok = False
            else:
                if q not in p.get("name", "").lower() and q not in p.get("description", "").lower():
                    ok = False

        if ok:
            results.append(p)

    return results


def find_product_by_ref(ref_text: str, candidates: Optional[List[Dict]] = None) -> Optional[Dict]:
    """
    Resolve references like 'second hoodie', 'black hoodie', 'phone-003' to a product.

    Heuristics:
    - Ordinals: first/second/third/fourth in a candidate list.
    - Exact id match.
    - Color + category.
    - Name substring.
    - Numeric index ('2' -> second).
    """
    ref = (ref_text or "").lower().strip()
    cand = candidates if candidates is not None else CATALOG

    # prefer mobiles if user mentions phone/mobile
    wants_mobile = any(w in ref for w in ("phone", "phones", "mobile", "mobiles"))
    filtered = cand
    if wants_mobile:
        filtered = [p for p in cand if p.get("category") == "mobile"] or cand

    ordinals = {"first": 0, "second": 1, "third": 2, "fourth": 3}
    for word, idx in ordinals.items():
        if word in ref and idx < len(filtered):
            return filtered[idx]

    # direct id match
    for p in cand:
        if p["id"].lower() == ref:
            return p

    # color + category combination
    for p in cand:
        if p.get("color") and p["color"].lower() in ref and p.get("category") and p["category"] in ref:
            return p

    # strong name substring
    tokens = [t for t in ref.split() if len(t) > 2]
    for p in filtered:
        name = p["name"].lower()
        if tokens and all(t in name for t in tokens):
            return p

    # weaker match
    for p in cand:
        name = p["name"].lower()
        if any(t in name for t in tokens):
            return p

    # numeric index
    for token in ref.split():
        if token.isdigit():
            idx = int(token) - 1
            if 0 <= idx < len(filtered):
                return filtered[idx]

    return None


def create_order_object(line_items: List[Dict], currency: str = "INR") -> Dict:
    """
    line_items: [{product_id, quantity, attrs}]
    Returns an order dict: {id, items, total, currency, created_at}
    and persists it to orders.json.
    """
    items: List[Dict] = []
    total = 0

    for li in line_items:
        pid = li.get("product_id")
        qty = int(li.get("quantity", 1))
        prod = next((p for p in CATALOG if p["id"] == pid), None)
        if not prod:
            raise ValueError(f"Product {pid} not found")
        line_total = prod["price"] * qty
        total += line_total
        items.append(
            {
                "product_id": pid,
                "name": prod["name"],
                "unit_price": prod["price"],
                "quantity": qty,
                "line_total": line_total,
                "attrs": li.get("attrs", {}),
            }
        )

    order = {
        "id": f"order-{str(uuid.uuid4())[:8]}",
        "items": items,
        "total": total,
        "currency": currency,
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    _save_order(order)
    return order


def get_most_recent_order() -> Optional[Dict]:
    all_orders = _load_all_orders()
    return all_orders[-1] if all_orders else None

# -------------------------
# TOOLS
# -------------------------

@function_tool
async def show_catalog(
    ctx: RunContext[Userdata],
    q: Annotated[Optional[str], Field(description="Search query (optional)", default=None)] = None,
    category: Annotated[Optional[str], Field(description="Category (optional)", default=None)] = None,
    max_price: Annotated[Optional[int], Field(description="Maximum price (optional)", default=None)] = None,
    color: Annotated[Optional[str], Field(description="Color (optional)", default=None)] = None,
) -> str:
    """
    Return a spoken summary of matching products (name, price, id).
    - Recognizes category synonyms like 'phones', 'tees'.
    - Returns up to 8 items.
    """
    # category auto-detect from query
    if not category and q:
        q_lower = q.lower()
        if any(w in q_lower for w in ("phone", "phones", "mobile", "mobiles")):
            category = "mobile"
        if any(w in q_lower for w in ("tee", "tshirt", "t-shirts", "tees")):
            category = "tshirt"

    filters = {"q": q, "category": category, "max_price": max_price, "color": color}
    prods = list_products({k: v for k, v in filters.items() if v is not None})

    if not prods:
        return "Sorry, I couldn't find any items that match. You can try a simpler request, like 'show phones under 20,000' or 'black hoodies'."

    lines = [f"Here are the top {min(8, len(prods))} items I found at Lalit's Shop:"]
    for idx, p in enumerate(prods[:8], start=1):
        size_info = f" (sizes: {', '.join(p['sizes'])})" if p.get("sizes") else ""
        lines.append(
            f"{idx}. {p['name']} — ₹{p['price']} {p['currency']} (id: {p['id']}){size_info}"
        )

    lines.append("You can say: 'Add the second item, size M, quantity 1' or 'add mug-001 to my cart, quantity 2'.")
    return "\n".join(lines)


@function_tool
async def add_to_cart(
    ctx: RunContext[Userdata],
    product_ref: Annotated[str, Field(description="Reference to product: id, name, or spoken ref")],
    quantity: Annotated[int, Field(description="Quantity", ge=1, default=1)] = 1,
    size: Annotated[Optional[str], Field(description="Size (optional, e.g. 'M')", default=None)] = None,
) -> str:
    """Resolve a product and add it to the session cart."""
    userdata = ctx.userdata
    product = find_product_by_ref(product_ref)
    if not product:
        return "I couldn't figure out which product you meant. Try using the product id, like 'add tee-002, size M'."

    if size and product.get("sizes") and size not in product["sizes"]:
        return f"{product['name']} is not available in size {size}. Available sizes are: {', '.join(product['sizes'])}."

    attrs = {}
    if size:
        attrs["size"] = size

    # merge with existing line item if same product+size
    for line in userdata.cart:
        if line["product_id"] == product["id"] and line.get("attrs", {}).get("size") == attrs.get("size"):
            line["quantity"] += quantity
            break
    else:
        userdata.cart.append(
            {
                "product_id": product["id"],
                "quantity": quantity,
                "attrs": attrs,
            }
        )

    # compute total
    total = 0
    for li in userdata.cart:
        prod = next((p for p in CATALOG if p["id"] == li["product_id"]), None)
        if prod:
            total += prod["price"] * li["quantity"]

    size_str = f" in size {size}" if size else ""
    return f"Added {quantity} x {product['name']}{size_str} to your cart. Current estimated total is around ₹{total}."


@function_tool
async def show_cart(
    ctx: RunContext[Userdata],
) -> str:
    """Speak out the current cart contents and total value."""
    userdata = ctx.userdata
    if not userdata.cart:
        return "Your cart is empty right now."

    lines: List[str] = []
    total = 0

    for idx, li in enumerate(userdata.cart, start=1):
        prod = next((p for p in CATALOG if p["id"] == li["product_id"]), None)
        if not prod:
            continue
        line_total = prod["price"] * li["quantity"]
        total += line_total
        size = li.get("attrs", {}).get("size")
        size_text = f", size {size}" if size else ""
        lines.append(
            f"{idx}. {prod['name']}{size_text} — {li['quantity']} x ₹{prod['price']} = ₹{line_total}"
        )

    lines.append(f"Total estimated amount: ₹{total}.")
    lines.append("You can say: 'place my order' or 'remove the second item from my cart'.")
    return "\n".join(lines)


@function_tool
async def place_order(
    ctx: RunContext[Userdata],
    customer_name: Annotated[Optional[str], Field(description="Customer name (optional)", default=None)] = None,
) -> str:
    """Convert the current cart into an order, persist it, and clear the cart."""
    userdata = ctx.userdata
    if not userdata.cart:
        return "Your cart is empty, so there's nothing to place yet."

    if customer_name:
        userdata.customer_name = customer_name.strip()

    try:
        order = create_order_object(userdata.cart)
    except ValueError as e:
        return f"Something went wrong while creating the order: {e}"

    userdata.orders.append(order)
    userdata.cart = []

    name = userdata.customer_name or "customer"
    return (
        f"Order placed successfully, {name}! 🎉\n"
        f"Order ID: {order['id']}\n"
        f"Total: ₹{order['total']} {order['currency']}\n"
        "You can ask: 'what was my last order' to hear the summary again."
    )


@function_tool
async def show_last_order(
    ctx: RunContext[Userdata],
) -> str:
    """Summarize the most recent order from the global orders log."""
    order = get_most_recent_order()
    if not order:
        return "There are no orders recorded yet."

    lines = [f"Most recent order: {order['id']} placed at {order['created_at']}."]
    total = order["total"]
    for idx, item in enumerate(order["items"], start=1):
        size = item.get("attrs", {}).get("size")
        size_txt = f", size {size}" if size else ""
        lines.append(
            f"{idx}. {item['name']}{size_txt} — {item['quantity']} x ₹{item['unit_price']} = ₹{item['line_total']}"
        )
    lines.append(f"Total: ₹{total} {order['currency']}.")
    return "\n".join(lines)


@function_tool
async def clear_cart(
    ctx: RunContext[Userdata],
) -> str:
    """Remove all items from the cart."""
    ctx.userdata.cart = []
    return "Your cart is now empty."

# -------------------------
# Agent Definition
# -------------------------

class ShoppingAgent(Agent):
    def __init__(self):
        super().__init__(
            instructions="""
            You are a friendly shopping assistant for **Lalit's Shop**.

            CATALOG:
            - You can sell mugs, t-shirts, hoodies, raincoats, laptops, storage devices, and mobile phones.
            - Prices are in Indian Rupees (INR).
            - Use the tools to query the catalog; do NOT invent unknown products or prices.

            GOALS:
            - Help the user discover products based on their needs and budget.
            - Help them build a cart (add items, show cart).
            - Let them place an order and hear a summary of the last order.
            - Keep answers short and clear, like a good salesperson on a voice call.

            TOOLS:
            - `show_catalog(q, category, max_price, color)` to list items.
            - `add_to_cart(product_ref, quantity, size)` to put items in the cart.
            - `show_cart()` to summarize their current cart.
            - `place_order(customer_name?)` to turn the cart into an order.
            - `show_last_order()` to recall the latest order.
            - `clear_cart()` to empty the cart.

            BEHAVIOR:
            - After suggesting items, gently guide the user: e.g., ask if they want to add one to the cart.
            - When the user says something like "I want a phone under 20k", call `show_catalog` with suitable filters.
            - When they say "add the second phone in black, quantity 1", call `add_to_cart`.

            SAFETY:
            - Do not talk about internal implementation, tools or JSON.
            - Stay within the catalog; if something isn't available, say so honestly.
            """,
            tools=[
                show_catalog,
                add_to_cart,
                show_cart,
                place_order,
                show_last_order,
                clear_cart,
            ],
        )

# -------------------------
# ENTRYPOINT & PREWARM
# -------------------------

def prewarm(proc: JobProcess):
    """Preload VAD model for lower latency."""
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}
    logger.info("🛒 Starting Lalit's Shop voice agent session")

    userdata = Userdata()

    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=murf.TTS(
            voice="en-US-natalie",
            style="Conversational",
            text_pacing=True,
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        userdata=userdata,
    )

    await session.start(
        agent=ShoppingAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC()
        ),
    )

    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
