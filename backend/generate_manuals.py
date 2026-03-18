"""
Generate StockBud user manuals (English + Hindi) as PDFs with annotated screenshots.
Uses reportlab for PDF generation and PIL for image annotation.
"""
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch, mm
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak,
    Table, TableStyle, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image as PILImage, ImageDraw, ImageFont
import textwrap

SCREENSHOTS_DIR = "/app/manual_screenshots"
OUTPUT_DIR = "/app/frontend/public/manuals"

# Colors
BLUE = HexColor("#2563eb")
DARK = HexColor("#1e293b")
GRAY = HexColor("#64748b")
LIGHT_BG = HexColor("#f1f5f9")
ACCENT = HexColor("#059669")
RED_ACCENT = HexColor("#dc2626")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Register Hindi-capable font (Noto Sans Devanagari)
HINDI_FONT_PATH = None
HINDI_FONT_PATHS = [
    "/usr/share/fonts/truetype/lohit-devanagari/Lohit-Devanagari.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

def register_fonts():
    """Try to register Hindi-capable fonts."""
    global HINDI_FONT_PATH
    for fp in HINDI_FONT_PATHS:
        if os.path.exists(fp):
            try:
                pdfmetrics.registerFont(TTFont('HindiFont', fp))
                HINDI_FONT_PATH = fp
                return True
            except Exception:
                continue
    return False

has_hindi_font = register_fonts()

def get_styles(lang='en'):
    """Get paragraph styles for PDF."""
    styles = getSampleStyleSheet()
    
    font_name = 'HindiFont' if (lang == 'hi' and has_hindi_font) else 'Helvetica'
    font_bold = 'HindiFont' if (lang == 'hi' and has_hindi_font) else 'Helvetica-Bold'
    
    styles.add(ParagraphStyle(
        name='ManualTitle',
        fontName=font_bold,
        fontSize=28,
        textColor=DARK,
        alignment=TA_CENTER,
        spaceAfter=6,
        leading=34,
    ))
    styles.add(ParagraphStyle(
        name='ManualSubtitle',
        fontName=font_name,
        fontSize=14,
        textColor=GRAY,
        alignment=TA_CENTER,
        spaceAfter=30,
        leading=18,
    ))
    styles.add(ParagraphStyle(
        name='SectionTitle',
        fontName=font_bold,
        fontSize=18,
        textColor=BLUE,
        spaceAfter=8,
        spaceBefore=4,
        leading=22,
    ))
    styles.add(ParagraphStyle(
        name='FeatureDesc',
        fontName=font_name,
        fontSize=10,
        textColor=DARK,
        spaceAfter=4,
        leading=14,
    ))
    styles.add(ParagraphStyle(
        name='BulletItem',
        fontName=font_name,
        fontSize=9,
        textColor=GRAY,
        leftIndent=15,
        spaceAfter=2,
        leading=12,
    ))
    styles.add(ParagraphStyle(
        name='Caption',
        fontName=font_name,
        fontSize=8,
        textColor=GRAY,
        alignment=TA_CENTER,
        spaceAfter=12,
        leading=10,
    ))
    styles.add(ParagraphStyle(
        name='PageFooter',
        fontName=font_name,
        fontSize=7,
        textColor=GRAY,
        alignment=TA_CENTER,
    ))
    return styles


def annotate_screenshot(img_path, annotations, output_path):
    """
    Draw arrows and labels on a screenshot.
    annotations: list of dicts with keys:
      - x, y: coordinates of the arrow target
      - label: text label
      - direction: 'left', 'right', 'up', 'down' (where the label appears relative to arrow)
    """
    img = PILImage.open(img_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    
    # Try to get a good font
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
        small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 13)
    except:
        font = ImageFont.load_default()
        small_font = font
    
    arrow_color = (220, 38, 38)  # Red
    bg_color = (254, 226, 226)  # Light red bg
    text_color = (30, 41, 59)  # Dark
    
    for ann in annotations:
        x, y = ann['x'], ann['y']
        label = ann['label']
        direction = ann.get('direction', 'right')
        
        # Draw circle at target
        r = 8
        draw.ellipse([x-r, y-r, x+r, y+r], fill=arrow_color, outline=arrow_color)
        draw.ellipse([x-r+3, y-r+3, x+r-3, y+r-3], fill=(255,255,255))
        
        # Calculate label position
        bbox = draw.textbbox((0, 0), label, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        padding = 6
        
        if direction == 'right':
            lx = x + 20
            ly = y - th // 2
            # Draw line from circle to label
            draw.line([(x + r, y), (lx - 2, y)], fill=arrow_color, width=2)
        elif direction == 'left':
            lx = x - 20 - tw - padding * 2
            ly = y - th // 2
            draw.line([(x - r, y), (lx + tw + padding * 2 + 2, y)], fill=arrow_color, width=2)
        elif direction == 'down':
            lx = x - tw // 2 - padding
            ly = y + 20
            draw.line([(x, y + r), (x, ly - 2)], fill=arrow_color, width=2)
        else:  # up
            lx = x - tw // 2 - padding
            ly = y - 20 - th - padding * 2
            draw.line([(x, y - r), (x, ly + th + padding * 2 + 2)], fill=arrow_color, width=2)
        
        # Draw label background
        draw.rounded_rectangle(
            [lx - padding, ly - padding, lx + tw + padding, ly + th + padding],
            radius=4,
            fill=bg_color,
            outline=arrow_color,
            width=1
        )
        draw.text((lx, ly), label, fill=text_color, font=font)
    
    img.save(output_path)
    return output_path


# ============================================================
# FEATURE DEFINITIONS (ordered least complex to most complex)
# ============================================================

FEATURES_EN = [
    {
        "title": "1. Login",
        "screenshot": "01_login",
        "desc": "Secure login screen for all users. Enter your username and password to access the system.",
        "bullets": [
            "Role-based access: Admin, Manager, Executive, Polythene Executive",
            "JWT authentication with 18-hour session expiry",
            "Each role sees only relevant pages after login",
        ],
        "annotations": [
            {"x": 720, "y": 330, "label": "Username", "direction": "right"},
            {"x": 720, "y": 400, "label": "Password", "direction": "right"},
            {"x": 720, "y": 470, "label": "Sign In Button", "direction": "right"},
        ],
    },
    {
        "title": "2. Dashboard",
        "screenshot": "02_dashboard",
        "desc": "Overview of your business at a glance. Shows transaction counts, date range, and stamp verification status.",
        "bullets": [
            "Transaction date range displayed in DD/MM/YYYY format",
            "Key stats: Total Transactions, Parties, Purchases, Sales",
            "Stamp verification status with overdue alerts",
            "Download user manual (English / Hindi) from top-right",
        ],
        "annotations": [
            {"x": 350, "y": 150, "label": "Stats Cards", "direction": "down"},
            {"x": 500, "y": 100, "label": "Date Range", "direction": "down"},
            {"x": 1300, "y": 48, "label": "Download Manual", "direction": "left"},
        ],
    },
    {
        "title": "3. Notifications",
        "screenshot": "23_notifications",
        "desc": "Central notification hub for stock alerts, order updates, and system messages.",
        "bullets": [
            "Stock deficit alerts with one-click Quick Order",
            "Order received/overdue notifications",
            "System upload notifications",
        ],
        "annotations": [
            {"x": 400, "y": 200, "label": "Notification List", "direction": "right"},
        ],
    },
    {
        "title": "4. Upload Files",
        "screenshot": "03_upload",
        "desc": "Upload Excel files for opening stock, purchase ledger, and sale ledger. Files are parsed in your browser.",
        "bullets": [
            "Drag & drop or click to select Excel files",
            "Supports: Opening Stock, Purchase Ledger, Sale Ledger, Physical Stock",
            "Real-time upload progress with serialized queue",
            "Files processed client-side — server never overloads",
        ],
        "annotations": [
            {"x": 720, "y": 280, "label": "File Type Selector", "direction": "right"},
            {"x": 720, "y": 420, "label": "Drop Zone", "direction": "right"},
        ],
    },
    {
        "title": "5. Current Stock",
        "screenshot": "04_current_stock",
        "desc": "Real-time view of all inventory items calculated as: Opening Stock + Purchases - Sales.",
        "bullets": [
            "Stamp-wise grouping for each item",
            "Search and filter by item name or stamp",
            "Negative stock items highlighted in red",
            "CSV export for all data",
        ],
        "annotations": [
            {"x": 400, "y": 120, "label": "Search", "direction": "right"},
            {"x": 1100, "y": 200, "label": "Stock Details", "direction": "left"},
        ],
    },
    {
        "title": "6. Item Mapping",
        "screenshot": "05_item_mapping",
        "desc": "Map raw transaction names to master item names to resolve naming inconsistencies.",
        "bullets": [
            "Auto-detect unmapped items from transactions",
            "Map e.g. 'JB-70 KADA CC' to 'JB-70 KADA II'",
            "Bulk mapping support",
        ],
        "annotations": [
            {"x": 500, "y": 250, "label": "Mapping Table", "direction": "right"},
        ],
    },
    {
        "title": "7. Manage Mappings",
        "screenshot": "06_mapping_management",
        "desc": "View and edit all existing item name mappings.",
        "bullets": [
            "Delete incorrect mappings",
            "Search across all mappings",
            "See which transaction names map to which master names",
        ],
        "annotations": [
            {"x": 600, "y": 200, "label": "Existing Mappings", "direction": "right"},
        ],
    },
    {
        "title": "8. Purchase Rates",
        "screenshot": "07_purchase_rates",
        "desc": "View cumulative purchase rates from the purchase ledger, used as cost basis for profit calculations.",
        "bullets": [
            "Shows average rate, tunch, and labour per item",
            "Automatically calculated from uploaded purchase data",
        ],
        "annotations": [
            {"x": 700, "y": 200, "label": "Purchase Rate Data", "direction": "down"},
        ],
    },
    {
        "title": "9. Stamp Management",
        "screenshot": "08_stamps",
        "desc": "Stamps represent physical trays/sections in your warehouse. Click any stamp to see its items.",
        "bullets": [
            "See all items in each stamp with total stock",
            "Click a stamp to drill down into item details",
            "Verification tracking per stamp",
        ],
        "annotations": [
            {"x": 400, "y": 300, "label": "Stamp Cards", "direction": "right"},
        ],
    },
    {
        "title": "10. Stamp Assignments",
        "screenshot": "09_stamp_assignments",
        "desc": "Assign stamps to sales executives. Each executive can only enter stock for their assigned stamps.",
        "bullets": [
            "One executive per stamp",
            "Admin controls all assignments",
        ],
        "annotations": [
            {"x": 700, "y": 250, "label": "Assignment Controls", "direction": "down"},
        ],
    },
    {
        "title": "11. Polythene Management",
        "screenshot": "18_polythene_mgmt",
        "desc": "Track polythene weight adjustments across items.",
        "bullets": [
            "Polythene executives can add/adjust polythene weight",
            "Admin sees all polythene entries",
        ],
        "annotations": [
            {"x": 600, "y": 200, "label": "Polythene Entries", "direction": "right"},
        ],
    },
    {
        "title": "12. Physical vs Book Comparison",
        "screenshot": "10_physical_vs_book",
        "desc": "Upload physical stock and compare it against calculated book stock to find discrepancies.",
        "bullets": [
            "Date-scoped comparison — each date is independent",
            "Shows differences with gross/net weight deltas",
            "Partial update preview with approve/reject workflow",
            "Stamp-aware matching with ambiguity detection",
        ],
        "annotations": [
            {"x": 400, "y": 150, "label": "Date Filter", "direction": "right"},
            {"x": 800, "y": 300, "label": "Comparison Table", "direction": "down"},
        ],
    },
    {
        "title": "13. Approvals",
        "screenshot": "11_approvals",
        "desc": "Manager/Admin approval queue for stock entries submitted by executives.",
        "bullets": [
            "Approve or reject executive stock entries",
            "See who submitted and when",
        ],
        "annotations": [
            {"x": 600, "y": 250, "label": "Approval Queue", "direction": "right"},
        ],
    },
    {
        "title": "14. Item Groups",
        "screenshot": "13_item_groups",
        "desc": "Merge interchangeable items so their stock and sales are combined under one group leader.",
        "bullets": [
            "Group leader appears in Current Stock, Buffers, Orders",
            "Auto-detect groupable items from mappings",
            "Consolidated numbers across group members",
        ],
        "annotations": [
            {"x": 500, "y": 250, "label": "Item Groups", "direction": "right"},
        ],
    },
    {
        "title": "15. Item Buffers & Seasonal Ordering",
        "screenshot": "12_item_buffers",
        "desc": "Auto-categorize items into velocity tiers and calculate smart buffer levels with seasonal adjustments.",
        "bullets": [
            "Tiers: Fastest, Fast, Medium, Slow, Dead",
            "Indian festival awareness: Diwali, Akshaya Tritiya, Wedding Season",
            "Season boost up to 1.5x during peak periods",
            "Red/Green/Yellow status for stock health",
        ],
        "annotations": [
            {"x": 400, "y": 200, "label": "Buffer Controls", "direction": "right"},
            {"x": 1000, "y": 300, "label": "Item Tiers", "direction": "left"},
        ],
    },
    {
        "title": "16. Orders",
        "screenshot": "14_orders",
        "desc": "Track orders from creation to receipt with overdue alerts.",
        "bullets": [
            "Quick Order from stock deficit alerts",
            "Suggested quantity range from buffer calculations",
            "Overdue orders (7+ days) highlighted in red",
            "Status tracking: Ordered to Received",
        ],
        "annotations": [
            {"x": 500, "y": 200, "label": "Order List", "direction": "right"},
            {"x": 1100, "y": 200, "label": "Status", "direction": "left"},
        ],
    },
    {
        "title": "17. Party Analytics",
        "screenshot": "15_party_analytics",
        "desc": "Customer-wise and supplier-wise transaction breakdown with volume analysis.",
        "bullets": [
            "Total weight traded per party",
            "Transaction counts and average rates",
            "Top customers/suppliers by volume",
        ],
        "annotations": [
            {"x": 600, "y": 300, "label": "Party Data", "direction": "right"},
        ],
    },
    {
        "title": "18. Profit Analysis",
        "screenshot": "16_profit",
        "desc": "Calculate silver profit (kg) and labour profit (Rs) from your transactions.",
        "bullets": [
            "Silver Profit = tunch difference between purchase and sale",
            "Labour Profit = labour charge difference per gram",
            "Views: Customer, Supplier, Item, Month, Year",
            "Historical profit from uploaded data",
        ],
        "annotations": [
            {"x": 400, "y": 150, "label": "Profit Tabs", "direction": "right"},
            {"x": 800, "y": 300, "label": "Profit Data", "direction": "down"},
        ],
    },
    {
        "title": "19. Data Visualization & AI",
        "screenshot": "17_visualization",
        "desc": "Charts, trends, and AI-powered insights for your inventory data.",
        "bullets": [
            "Sales trends, purchase trends, inventory health",
            "AI Smart Insights — ask questions in natural language",
            "Seasonal analysis with festival calendar",
        ],
        "annotations": [
            {"x": 700, "y": 300, "label": "Charts & AI", "direction": "down"},
        ],
    },
    {
        "title": "20. Historical Upload",
        "screenshot": "22_historical_upload",
        "desc": "Upload large historical Excel files (200K+ rows). Data is kept separate from current stock.",
        "bullets": [
            "Client-side parsing — handles 24MB+ files",
            "Batch upload with real-time progress",
            "Historical data does not affect current stock",
        ],
        "annotations": [
            {"x": 700, "y": 300, "label": "Upload Area", "direction": "down"},
        ],
    },
    {
        "title": "21. User Management",
        "screenshot": "19_users",
        "desc": "Admin panel to create and manage user accounts with role assignments.",
        "bullets": [
            "Create users with specific roles",
            "Activate/deactivate accounts",
            "Change passwords and usernames",
        ],
        "annotations": [
            {"x": 500, "y": 200, "label": "User List", "direction": "right"},
            {"x": 1100, "y": 200, "label": "Actions", "direction": "left"},
        ],
    },
    {
        "title": "22. History & Activity Log",
        "screenshot": "20_history",
        "desc": "Complete audit trail of all uploads and system actions.",
        "bullets": [
            "Upload history with undo capability",
            "Activity log tracks all user actions",
            "Timestamp and user info for every action",
        ],
        "annotations": [
            {"x": 600, "y": 200, "label": "Upload History", "direction": "right"},
        ],
    },
]

FEATURES_HI = [
    {
        "title": "1. \u0932\u0949\u0917\u0907\u0928 (Login)",
        "screenshot": "01_login",
        "desc": "\u0938\u092d\u0940 \u092f\u0942\u091c\u093c\u0930\u094d\u0938 \u0915\u0947 \u0932\u093f\u090f \u0938\u0941\u0930\u0915\u094d\u0937\u093f\u0924 \u0932\u0949\u0917\u0907\u0928 \u0938\u094d\u0915\u094d\u0930\u0940\u0928\u0964 \u0905\u092a\u0928\u093e \u092f\u0942\u091c\u093c\u0930\u0928\u0947\u092e \u0914\u0930 \u092a\u093e\u0938\u0935\u0930\u094d\u0921 \u0921\u093e\u0932\u0947\u0902\u0964",
        "bullets": [
            "\u0930\u094b\u0932-\u092c\u0947\u0938\u094d\u0921 \u090f\u0915\u094d\u0938\u0947\u0938: Admin, Manager, Executive, Polythene Executive",
            "JWT \u0911\u0925\u0947\u0902\u091f\u093f\u0915\u0947\u0936\u0928, 18 \u0918\u0902\u091f\u0947 \u0915\u0940 \u0938\u0947\u0936\u0928 \u090f\u0915\u094d\u0938\u092a\u093e\u092f\u0930\u0940",
            "\u0939\u0930 \u0930\u094b\u0932 \u0915\u094b \u0932\u0949\u0917\u0907\u0928 \u0915\u0947 \u092c\u093e\u0926 \u0938\u093f\u0930\u094d\u092b \u0909\u0928\u0915\u0947 \u0932\u093f\u090f \u0930\u0947\u0932\u0947\u0935\u0947\u0902\u091f \u092a\u0947\u091c \u0926\u093f\u0916\u0924\u0947 \u0939\u0948\u0902",
        ],
        "annotations": [
            {"x": 720, "y": 330, "label": "Username", "direction": "right"},
            {"x": 720, "y": 400, "label": "Password", "direction": "right"},
            {"x": 720, "y": 470, "label": "Sign In", "direction": "right"},
        ],
    },
    {
        "title": "2. \u0921\u0948\u0936\u092c\u094b\u0930\u094d\u0921 (Dashboard)",
        "screenshot": "02_dashboard",
        "desc": "\u0906\u092a\u0915\u0947 \u092c\u093f\u091c\u093c\u0928\u0947\u0938 \u0915\u093e \u0938\u093e\u0930\u093e\u0902\u0936\u0964 \u091f\u094d\u0930\u093e\u0902\u091c\u0947\u0915\u094d\u0936\u0928 \u0915\u093e\u0909\u0902\u091f, \u0924\u093e\u0930\u0940\u0916 \u0930\u0947\u0902\u091c \u0914\u0930 \u0938\u094d\u091f\u0948\u0902\u092a \u0935\u0947\u0930\u093f\u092b\u093f\u0915\u0947\u0936\u0928 \u0938\u094d\u091f\u0947\u091f\u0938 \u0926\u093f\u0916\u093e\u0924\u093e \u0939\u0948\u0964",
        "bullets": [
            "\u091f\u094d\u0930\u093e\u0902\u091c\u0947\u0915\u094d\u0936\u0928 \u0924\u093e\u0930\u0940\u0916 DD/MM/YYYY \u092b\u0949\u0930\u094d\u092e\u0947\u091f \u092e\u0947\u0902",
            "\u092e\u0941\u0916\u094d\u092f \u0906\u0902\u0915\u0921\u093c\u0947: \u0915\u0941\u0932 \u091f\u094d\u0930\u093e\u0902\u091c\u0947\u0915\u094d\u0936\u0928, \u092a\u093e\u0930\u094d\u091f\u0940\u091c\u093c, \u0916\u0930\u0940\u0926, \u092c\u093f\u0915\u094d\u0930\u0940",
            "\u0938\u094d\u091f\u0948\u0902\u092a \u0935\u0947\u0930\u093f\u092b\u093f\u0915\u0947\u0936\u0928 \u0938\u094d\u091f\u0947\u091f\u0938 \u0913\u0935\u0930\u0921\u094d\u092f\u0942 \u0905\u0932\u0930\u094d\u091f \u0915\u0947 \u0938\u093e\u0925",
            "\u092e\u0948\u0928\u094d\u092f\u0941\u0905\u0932 \u0921\u093e\u0909\u0928\u0932\u094b\u0921 (\u0905\u0902\u0917\u094d\u0930\u0947\u091c\u093c\u0940/\u0939\u093f\u0902\u0926\u0940) \u090a\u092a\u0930 \u0926\u093e\u0908\u0902 \u0924\u0930\u092b \u0938\u0947",
        ],
        "annotations": [
            {"x": 350, "y": 150, "label": "Stats Cards", "direction": "down"},
            {"x": 500, "y": 100, "label": "Date Range", "direction": "down"},
            {"x": 1300, "y": 48, "label": "Manual Download", "direction": "left"},
        ],
    },
    {
        "title": "3. \u0928\u094b\u091f\u093f\u092b\u093f\u0915\u0947\u0936\u0928 (Notifications)",
        "screenshot": "23_notifications",
        "desc": "\u0938\u094d\u091f\u0949\u0915 \u0905\u0932\u0930\u094d\u091f, \u0911\u0930\u094d\u0921\u0930 \u0905\u092a\u0921\u0947\u091f \u0914\u0930 \u0938\u093f\u0938\u094d\u091f\u092e \u092e\u0948\u0938\u0947\u091c\u0947\u091c\u093c \u0915\u093e \u0915\u0947\u0902\u0926\u094d\u0930\u0940\u092f \u0939\u092c\u0964",
        "bullets": [
            "\u0938\u094d\u091f\u0949\u0915 \u0915\u092e\u0940 \u0915\u0940 \u0905\u0932\u0930\u094d\u091f \u0915\u0947 \u0938\u093e\u0925 \u090f\u0915-\u0915\u094d\u0932\u093f\u0915 \u0915\u094d\u0935\u093f\u0915 \u0911\u0930\u094d\u0921\u0930",
            "\u0911\u0930\u094d\u0921\u0930 \u092a\u094d\u0930\u093e\u092a\u094d\u0924/\u0913\u0935\u0930\u0921\u094d\u092f\u0942 \u0928\u094b\u091f\u093f\u092b\u093f\u0915\u0947\u0936\u0928",
        ],
        "annotations": [
            {"x": 400, "y": 200, "label": "Notifications", "direction": "right"},
        ],
    },
    {
        "title": "4. \u092b\u093e\u0907\u0932 \u0905\u092a\u0932\u094b\u0921 (Upload Files)",
        "screenshot": "03_upload",
        "desc": "\u0913\u092a\u0928\u093f\u0902\u0917 \u0938\u094d\u091f\u0949\u0915, \u0916\u0930\u0940\u0926 \u0932\u0947\u091c\u0930 \u0914\u0930 \u092c\u093f\u0915\u094d\u0930\u0940 \u0932\u0947\u091c\u0930 \u0915\u0940 Excel \u092b\u093e\u0907\u0932\u0947\u0902 \u0905\u092a\u0932\u094b\u0921 \u0915\u0930\u0947\u0902\u0964",
        "bullets": [
            "\u0921\u094d\u0930\u0948\u0917 \u0905\u0902\u0921 \u0921\u094d\u0930\u0949\u092a \u092f\u093e \u0915\u094d\u0932\u093f\u0915 \u0915\u0930\u0915\u0947 Excel \u092b\u093e\u0907\u0932 \u091a\u0941\u0928\u0947\u0902",
            "\u0938\u092a\u094b\u0930\u094d\u091f: Opening Stock, Purchase Ledger, Sale Ledger, Physical Stock",
            "\u0930\u093f\u092f\u0932-\u091f\u093e\u0907\u092e \u092a\u094d\u0930\u094b\u0917\u094d\u0930\u0947\u0938 \u092c\u093e\u0930",
            "\u092b\u093e\u0907\u0932 \u092c\u094d\u0930\u093e\u0909\u091c\u093c\u0930 \u092e\u0947\u0902 \u092a\u094d\u0930\u094b\u0938\u0947\u0938 \u0939\u094b\u0924\u0940 \u0939\u0948 \u2014 \u0938\u0930\u094d\u0935\u0930 \u092a\u0930 \u0932\u094b\u0921 \u0928\u0939\u0940\u0902 \u0906\u0924\u093e",
        ],
        "annotations": [
            {"x": 720, "y": 280, "label": "File Type", "direction": "right"},
            {"x": 720, "y": 420, "label": "Drop Zone", "direction": "right"},
        ],
    },
    {
        "title": "5. \u0915\u0930\u0902\u091f \u0938\u094d\u091f\u0949\u0915 (Current Stock)",
        "screenshot": "04_current_stock",
        "desc": "\u0938\u092d\u0940 \u0906\u0907\u091f\u092e\u094d\u0938 \u0915\u0940 \u0930\u093f\u092f\u0932-\u091f\u093e\u0907\u092e \u0907\u0928\u094d\u0935\u0947\u0902\u091f\u0930\u0940: \u0913\u092a\u0928\u093f\u0902\u0917 \u0938\u094d\u091f\u0949\u0915 + \u0916\u0930\u0940\u0926 - \u092c\u093f\u0915\u094d\u0930\u0940",
        "bullets": [
            "\u0938\u094d\u091f\u0948\u0902\u092a-\u0935\u093e\u0907\u091c\u093c \u0917\u094d\u0930\u0942\u092a\u093f\u0902\u0917",
            "\u0928\u093e\u092e \u092f\u093e \u0938\u094d\u091f\u0948\u0902\u092a \u0938\u0947 \u0938\u0930\u094d\u091a \u0914\u0930 \u092b\u093f\u0932\u094d\u091f\u0930",
            "\u0928\u0947\u0917\u0947\u091f\u093f\u0935 \u0938\u094d\u091f\u0949\u0915 \u0932\u093e\u0932 \u0930\u0902\u0917 \u092e\u0947\u0902 \u0939\u093e\u0907\u0932\u093e\u0907\u091f",
            "CSV \u090f\u0915\u094d\u0938\u092a\u094b\u0930\u094d\u091f",
        ],
        "annotations": [
            {"x": 400, "y": 120, "label": "Search", "direction": "right"},
            {"x": 1100, "y": 200, "label": "Stock Details", "direction": "left"},
        ],
    },
    {
        "title": "6. \u0906\u0907\u091f\u092e \u092e\u0948\u092a\u093f\u0902\u0917 (Item Mapping)",
        "screenshot": "05_item_mapping",
        "desc": "\u091f\u094d\u0930\u093e\u0902\u091c\u0947\u0915\u094d\u0936\u0928 \u0928\u093e\u092e\u094b\u0902 \u0915\u094b \u092e\u093e\u0938\u094d\u091f\u0930 \u0906\u0907\u091f\u092e \u0928\u093e\u092e\u094b\u0902 \u0938\u0947 \u092e\u0948\u092a \u0915\u0930\u0947\u0902\u0964",
        "bullets": [
            "\u0905\u0928\u092e\u0948\u092a\u094d\u0921 \u0906\u0907\u091f\u092e \u0911\u091f\u094b-\u0921\u093f\u091f\u0947\u0915\u094d\u091f",
            "\u091c\u0948\u0938\u0947 'JB-70 KADA CC' \u0915\u094b 'JB-70 KADA II' \u0938\u0947 \u092e\u0948\u092a \u0915\u0930\u0947\u0902",
            "\u092c\u0932\u094d\u0915 \u092e\u0948\u092a\u093f\u0902\u0917 \u0938\u092a\u094b\u0930\u094d\u091f",
        ],
        "annotations": [
            {"x": 500, "y": 250, "label": "Mapping Table", "direction": "right"},
        ],
    },
    {
        "title": "7. \u092e\u0948\u092a\u093f\u0902\u0917 \u092a\u094d\u0930\u092c\u0902\u0927\u0928 (Manage Mappings)",
        "screenshot": "06_mapping_management",
        "desc": "\u092e\u094c\u091c\u0942\u0926\u093e \u0938\u092d\u0940 \u092e\u0948\u092a\u093f\u0902\u0917 \u0926\u0947\u0916\u0947\u0902 \u0914\u0930 \u090f\u0921\u093f\u091f \u0915\u0930\u0947\u0902\u0964",
        "bullets": [
            "\u0917\u0932\u0924 \u092e\u0948\u092a\u093f\u0902\u0917 \u0921\u093f\u0932\u0940\u091f \u0915\u0930\u0947\u0902",
            "\u0938\u092d\u0940 \u092e\u0948\u092a\u093f\u0902\u0917 \u092e\u0947\u0902 \u0938\u0930\u094d\u091a \u0915\u0930\u0947\u0902",
        ],
        "annotations": [
            {"x": 600, "y": 200, "label": "Mappings", "direction": "right"},
        ],
    },
    {
        "title": "8. \u0916\u0930\u0940\u0926 \u0926\u0930\u0947\u0902 (Purchase Rates)",
        "screenshot": "07_purchase_rates",
        "desc": "\u0916\u0930\u0940\u0926 \u0932\u0947\u091c\u0930 \u0938\u0947 \u0938\u0902\u091a\u092f\u0940 \u0916\u0930\u0940\u0926 \u0926\u0930\u0947\u0902 \u0926\u0947\u0916\u0947\u0902\u0964 \u0932\u093e\u092d \u0917\u0923\u0928\u093e \u092e\u0947\u0902 \u0915\u0949\u0938\u094d\u091f \u092c\u0947\u0938\u093f\u0938 \u0915\u0947 \u0930\u0942\u092a \u092e\u0947\u0902 \u0909\u092a\u092f\u094b\u0917\u0964",
        "bullets": [
            "\u092a\u094d\u0930\u0924\u093f \u0906\u0907\u091f\u092e \u0914\u0938\u0924 \u0930\u0947\u091f, \u091f\u0902\u091a \u0914\u0930 \u0932\u0947\u092c\u0930",
            "\u0905\u092a\u0932\u094b\u0921 \u0915\u093f\u090f \u0917\u090f \u0916\u0930\u0940\u0926 \u0921\u0947\u091f\u093e \u0938\u0947 \u0911\u091f\u094b\u092e\u0948\u091f\u093f\u0915 \u0917\u0923\u0928\u093e",
        ],
        "annotations": [
            {"x": 700, "y": 200, "label": "Purchase Rates", "direction": "down"},
        ],
    },
    {
        "title": "9. \u0938\u094d\u091f\u0948\u0902\u092a \u092a\u094d\u0930\u092c\u0902\u0927\u0928 (Stamp Management)",
        "screenshot": "08_stamps",
        "desc": "\u0938\u094d\u091f\u0948\u0902\u092a = \u0906\u092a\u0915\u0947 \u0917\u094b\u0926\u093e\u092e \u092e\u0947\u0902 \u092b\u093f\u091c\u093c\u093f\u0915\u0932 \u091f\u094d\u0930\u0947/\u0938\u0947\u0915\u094d\u0936\u0928\u0964 \u0915\u093f\u0938\u0940 \u092d\u0940 \u0938\u094d\u091f\u0948\u0902\u092a \u092a\u0930 \u0915\u094d\u0932\u093f\u0915 \u0915\u0930\u0947\u0902\u0964",
        "bullets": [
            "\u0939\u0930 \u0938\u094d\u091f\u0948\u0902\u092a \u092e\u0947\u0902 \u0938\u092d\u0940 \u0906\u0907\u091f\u092e \u0914\u0930 \u0915\u0941\u0932 \u0938\u094d\u091f\u0949\u0915 \u0926\u0947\u0916\u0947\u0902",
            "\u0935\u0947\u0930\u093f\u092b\u093f\u0915\u0947\u0936\u0928 \u091f\u094d\u0930\u0948\u0915\u093f\u0902\u0917",
        ],
        "annotations": [
            {"x": 400, "y": 300, "label": "Stamp Cards", "direction": "right"},
        ],
    },
    {
        "title": "10. \u0938\u094d\u091f\u0948\u0902\u092a \u0905\u0938\u093e\u0907\u0928\u092e\u0947\u0902\u091f (Stamp Assignments)",
        "screenshot": "09_stamp_assignments",
        "desc": "\u0938\u094d\u091f\u0948\u0902\u092a \u0915\u094b \u0938\u0947\u0932\u094d\u0938 \u090f\u0915\u094d\u091c\u0940\u0915\u094d\u092f\u0942\u091f\u093f\u0935 \u0915\u094b \u0905\u0938\u093e\u0907\u0928 \u0915\u0930\u0947\u0902\u0964",
        "bullets": [
            "\u090f\u0915 \u0938\u094d\u091f\u0948\u0902\u092a \u092a\u0930 \u090f\u0915 \u090f\u0915\u094d\u091c\u0940\u0915\u094d\u092f\u0942\u091f\u093f\u0935",
            "\u090f\u0921\u092e\u093f\u0928 \u0938\u092d\u0940 \u0905\u0938\u093e\u0907\u0928\u092e\u0947\u0902\u091f \u0915\u0902\u091f\u094d\u0930\u094b\u0932 \u0915\u0930\u0924\u093e \u0939\u0948",
        ],
        "annotations": [
            {"x": 700, "y": 250, "label": "Assignments", "direction": "down"},
        ],
    },
    {
        "title": "11. \u092a\u0949\u0932\u0940\u0925\u0940\u0928 \u092a\u094d\u0930\u092c\u0902\u0927\u0928 (Polythene Management)",
        "screenshot": "18_polythene_mgmt",
        "desc": "\u092a\u0949\u0932\u0940\u0925\u0940\u0928 \u0935\u091c\u0928 \u090f\u0921\u091c\u0938\u094d\u091f\u092e\u0947\u0902\u091f \u091f\u094d\u0930\u0948\u0915 \u0915\u0930\u0947\u0902\u0964",
        "bullets": [
            "\u092a\u0949\u0932\u0940\u0925\u0940\u0928 \u090f\u0915\u094d\u091c\u0940\u0915\u094d\u092f\u0942\u091f\u093f\u0935 \u0935\u091c\u0928 \u091c\u094b\u0921\u093c/\u090f\u0921\u091c\u0938\u094d\u091f \u0915\u0930 \u0938\u0915\u0924\u093e \u0939\u0948",
            "\u090f\u0921\u092e\u093f\u0928 \u0938\u092d\u0940 \u090f\u0902\u091f\u094d\u0930\u0940\u091c\u093c \u0926\u0947\u0916 \u0938\u0915\u0924\u093e \u0939\u0948",
        ],
        "annotations": [
            {"x": 600, "y": 200, "label": "Polythene Entries", "direction": "right"},
        ],
    },
    {
        "title": "12. \u092b\u093f\u091c\u093c\u093f\u0915\u0932 vs \u092c\u0941\u0915 \u0924\u0941\u0932\u0928\u093e (Physical vs Book)",
        "screenshot": "10_physical_vs_book",
        "desc": "\u092b\u093f\u091c\u093c\u093f\u0915\u0932 \u0938\u094d\u091f\u0949\u0915 \u0905\u092a\u0932\u094b\u0921 \u0915\u0930\u0947\u0902 \u0914\u0930 \u092c\u0941\u0915 \u0938\u094d\u091f\u0949\u0915 \u0938\u0947 \u0924\u0941\u0932\u0928\u093e \u0915\u0930\u0947\u0902\u0964",
        "bullets": [
            "\u0924\u093e\u0930\u0940\u0916-\u0938\u094d\u0915\u094b\u092a\u094d\u0921 \u0924\u0941\u0932\u0928\u093e \u2014 \u0939\u0930 \u0924\u093e\u0930\u0940\u0916 \u0938\u094d\u0935\u0924\u0902\u0924\u094d\u0930",
            "\u0917\u094d\u0930\u0949\u0938/\u0928\u0947\u091f \u0935\u0947\u091f \u0921\u0947\u0932\u094d\u091f\u093e \u0926\u093f\u0916\u093e\u0924\u093e \u0939\u0948",
            "\u092a\u093e\u0930\u094d\u0936\u093f\u092f\u0932 \u0905\u092a\u0921\u0947\u091f \u092a\u094d\u0930\u0940\u0935\u094d\u092f\u0942 \u0915\u0947 \u0938\u093e\u0925 \u0905\u092a\u094d\u0930\u0942\u0935/\u0930\u093f\u091c\u0947\u0915\u094d\u091f",
            "\u0938\u094d\u091f\u0948\u0902\u092a-\u0905\u0935\u0947\u092f\u0930 \u092e\u0948\u091a\u093f\u0902\u0917",
        ],
        "annotations": [
            {"x": 400, "y": 150, "label": "Date Filter", "direction": "right"},
            {"x": 800, "y": 300, "label": "Comparison", "direction": "down"},
        ],
    },
    {
        "title": "13. \u0905\u092a\u094d\u0930\u0942\u0935\u0932 (Approvals)",
        "screenshot": "11_approvals",
        "desc": "\u090f\u0915\u094d\u091c\u0940\u0915\u094d\u092f\u0942\u091f\u093f\u0935 \u0926\u094d\u0935\u093e\u0930\u093e \u0938\u092c\u092e\u093f\u091f \u0938\u094d\u091f\u0949\u0915 \u090f\u0902\u091f\u094d\u0930\u0940\u091c\u093c \u0915\u093e \u0905\u092a\u094d\u0930\u0942\u0935\u0932 \u0915\u094d\u092f\u0942\u0964",
        "bullets": [
            "\u0938\u094d\u091f\u0949\u0915 \u090f\u0902\u091f\u094d\u0930\u0940 \u0905\u092a\u094d\u0930\u0942\u0935 \u092f\u093e \u0930\u093f\u091c\u0947\u0915\u094d\u091f \u0915\u0930\u0947\u0902",
            "\u0915\u093f\u0938\u0928\u0947 \u0914\u0930 \u0915\u092c \u0938\u092c\u092e\u093f\u091f \u0915\u093f\u092f\u093e \u0926\u0947\u0916\u0947\u0902",
        ],
        "annotations": [
            {"x": 600, "y": 250, "label": "Approval Queue", "direction": "right"},
        ],
    },
    {
        "title": "14. \u0906\u0907\u091f\u092e \u0917\u094d\u0930\u0942\u092a\u094d\u0938 (Item Groups)",
        "screenshot": "13_item_groups",
        "desc": "\u090f\u0915 \u091c\u0948\u0938\u0947 \u0906\u0907\u091f\u092e \u092e\u0930\u094d\u091c \u0915\u0930\u0947\u0902 \u0924\u093e\u0915\u093f \u0909\u0928\u0915\u093e \u0938\u094d\u091f\u0949\u0915 \u0914\u0930 \u092c\u093f\u0915\u094d\u0930\u0940 \u0938\u0902\u092f\u0941\u0915\u094d\u0924 \u0926\u093f\u0916\u0947\u0964",
        "bullets": [
            "\u0917\u094d\u0930\u0942\u092a \u0932\u0940\u0921\u0930 \u0915\u0930\u0902\u091f \u0938\u094d\u091f\u0949\u0915, \u092c\u092b\u0930\u094d\u0938, \u0911\u0930\u094d\u0921\u0930\u094d\u0938 \u092e\u0947\u0902 \u0926\u093f\u0916\u0924\u093e \u0939\u0948",
            "\u092e\u0948\u092a\u093f\u0902\u0917 \u0938\u0947 \u0917\u094d\u0930\u0942\u092a\u0947\u092c\u0932 \u0906\u0907\u091f\u092e \u0911\u091f\u094b-\u0921\u093f\u091f\u0947\u0915\u094d\u091f",
        ],
        "annotations": [
            {"x": 500, "y": 250, "label": "Item Groups", "direction": "right"},
        ],
    },
    {
        "title": "15. \u0906\u0907\u091f\u092e \u092c\u092b\u0930 \u0914\u0930 \u0938\u0940\u091c\u093c\u0928\u0932 \u0911\u0930\u094d\u0921\u0930\u093f\u0902\u0917 (Buffers)",
        "screenshot": "12_item_buffers",
        "desc": "\u0906\u0907\u091f\u092e\u094d\u0938 \u0915\u094b \u0935\u0947\u0932\u0949\u0938\u093f\u091f\u0940 \u091f\u093f\u092f\u0930\u094d\u0938 \u092e\u0947\u0902 \u092c\u093e\u0902\u091f\u0947\u0902 \u0914\u0930 \u0938\u0940\u091c\u093c\u0928\u0932 \u090f\u0921\u091c\u0938\u094d\u091f\u092e\u0947\u0902\u091f \u0915\u0947 \u0938\u093e\u0925 \u092c\u092b\u0930 \u0932\u0947\u0935\u0932 \u0915\u0948\u0932\u0915\u0941\u0932\u0947\u091f \u0915\u0930\u0947\u0902\u0964",
        "bullets": [
            "\u091f\u093f\u092f\u0930: Fastest, Fast, Medium, Slow, Dead",
            "\u092d\u093e\u0930\u0924\u0940\u092f \u0924\u094d\u092f\u094b\u0939\u093e\u0930: \u0926\u093f\u0935\u093e\u0932\u0940, \u0905\u0915\u094d\u0937\u092f \u0924\u0943\u0924\u0940\u092f\u093e, \u0936\u093e\u0926\u0940 \u0915\u093e \u0938\u0940\u091c\u093c\u0928",
            "\u0938\u0940\u091c\u093c\u0928 \u092c\u0942\u0938\u094d\u091f \u0926\u093f\u0935\u093e\u0932\u0940 \u092e\u0947\u0902 1.5x \u0924\u0915",
            "\u0932\u093e\u0932/\u0939\u0930\u093e/\u092a\u0940\u0932\u093e \u0938\u094d\u091f\u0947\u091f\u0938",
        ],
        "annotations": [
            {"x": 400, "y": 200, "label": "Buffer Controls", "direction": "right"},
            {"x": 1000, "y": 300, "label": "Item Tiers", "direction": "left"},
        ],
    },
    {
        "title": "16. \u0911\u0930\u094d\u0921\u0930\u094d\u0938 (Orders)",
        "screenshot": "14_orders",
        "desc": "\u0911\u0930\u094d\u0921\u0930 \u092c\u0928\u093e\u0928\u0947 \u0938\u0947 \u092a\u094d\u0930\u093e\u092a\u094d\u0924\u093f \u0924\u0915 \u091f\u094d\u0930\u0948\u0915 \u0915\u0930\u0947\u0902\u0964",
        "bullets": [
            "\u0938\u094d\u091f\u0949\u0915 \u0915\u092e\u0940 \u0938\u0947 \u0915\u094d\u0935\u093f\u0915 \u0911\u0930\u094d\u0921\u0930",
            "\u092c\u092b\u0930 \u0917\u0923\u0928\u093e \u0938\u0947 \u0938\u0941\u091d\u093e\u0908 \u0917\u0908 \u092e\u093e\u0924\u094d\u0930\u093e",
            "7+ \u0926\u093f\u0928 \u0915\u0947 \u0913\u0935\u0930\u0921\u094d\u092f\u0942 \u0911\u0930\u094d\u0921\u0930 \u0932\u093e\u0932 \u092e\u0947\u0902",
        ],
        "annotations": [
            {"x": 500, "y": 200, "label": "Order List", "direction": "right"},
            {"x": 1100, "y": 200, "label": "Status", "direction": "left"},
        ],
    },
    {
        "title": "17. \u092a\u093e\u0930\u094d\u091f\u0940 \u090f\u0928\u093e\u0932\u093f\u091f\u093f\u0915\u094d\u0938 (Party Analytics)",
        "screenshot": "15_party_analytics",
        "desc": "\u0917\u094d\u0930\u093e\u0939\u0915 \u0914\u0930 \u0938\u092a\u094d\u0932\u093e\u092f\u0930 \u0935\u093e\u0907\u091c\u093c \u091f\u094d\u0930\u093e\u0902\u091c\u0947\u0915\u094d\u0936\u0928 \u092c\u094d\u0930\u0947\u0915\u0921\u093e\u0909\u0928\u0964",
        "bullets": [
            "\u092a\u094d\u0930\u0924\u093f \u092a\u093e\u0930\u094d\u091f\u0940 \u0915\u0941\u0932 \u0935\u091c\u0928, \u091f\u094d\u0930\u093e\u0902\u091c\u0947\u0915\u094d\u0936\u0928 \u0915\u093e\u0909\u0902\u091f, \u0914\u0938\u0924 \u0926\u0930\u0947\u0902",
            "\u0935\u0949\u0932\u094d\u092f\u0942\u092e \u0915\u0947 \u0906\u0927\u093e\u0930 \u092a\u0930 \u091f\u0949\u092a \u0917\u094d\u0930\u093e\u0939\u0915/\u0938\u092a\u094d\u0932\u093e\u092f\u0930",
        ],
        "annotations": [
            {"x": 600, "y": 300, "label": "Party Data", "direction": "right"},
        ],
    },
    {
        "title": "18. \u0932\u093e\u092d \u0935\u093f\u0936\u094d\u0932\u0947\u0937\u0923 (Profit Analysis)",
        "screenshot": "16_profit",
        "desc": "\u0938\u093f\u0932\u094d\u0935\u0930 \u092a\u094d\u0930\u0949\u092b\u093f\u091f (kg) \u0914\u0930 \u0932\u0947\u092c\u0930 \u092a\u094d\u0930\u0949\u092b\u093f\u091f (\u20b9) \u0915\u0940 \u0917\u0923\u0928\u093e \u0915\u0930\u0947\u0902\u0964",
        "bullets": [
            "\u0938\u093f\u0932\u094d\u0935\u0930 \u092a\u094d\u0930\u0949\u092b\u093f\u091f = \u0916\u0930\u0940\u0926 \u0914\u0930 \u092c\u093f\u0915\u094d\u0930\u0940 \u0915\u0947 \u092c\u0940\u091a \u091f\u0902\u091a \u0915\u093e \u0905\u0902\u0924\u0930",
            "\u0932\u0947\u092c\u0930 \u092a\u094d\u0930\u0949\u092b\u093f\u091f = \u092a\u094d\u0930\u0924\u093f \u0917\u094d\u0930\u093e\u092e \u0932\u0947\u092c\u0930 \u091a\u093e\u0930\u094d\u091c \u0915\u093e \u0905\u0902\u0924\u0930",
            "\u0935\u094d\u092f\u0942: \u0917\u094d\u0930\u093e\u0939\u0915, \u0938\u092a\u094d\u0932\u093e\u092f\u0930, \u0906\u0907\u091f\u092e, \u092e\u0939\u0940\u0928\u093e, \u0935\u093e\u0930\u094d\u0937\u093f\u0915",
        ],
        "annotations": [
            {"x": 400, "y": 150, "label": "Profit Tabs", "direction": "right"},
            {"x": 800, "y": 300, "label": "Profit Data", "direction": "down"},
        ],
    },
    {
        "title": "19. \u0921\u0947\u091f\u093e \u0935\u093f\u091c\u093c\u0941\u0905\u0932\u093e\u0907\u091c\u093c\u0947\u0936\u0928 \u0914\u0930 AI (Visualization & AI)",
        "screenshot": "17_visualization",
        "desc": "\u091a\u093e\u0930\u094d\u091f\u094d\u0938, \u091f\u094d\u0930\u0947\u0902\u0921\u094d\u0938, \u0914\u0930 AI-\u0938\u0902\u091a\u093e\u0932\u093f\u0924 \u0907\u0928\u0938\u093e\u0907\u091f\u094d\u0938\u0964",
        "bullets": [
            "\u092c\u093f\u0915\u094d\u0930\u0940 \u091f\u094d\u0930\u0947\u0902\u0921, \u0916\u0930\u0940\u0926 \u091f\u094d\u0930\u0947\u0902\u0921, \u0907\u0928\u094d\u0935\u0947\u0902\u091f\u0930\u0940 \u0939\u0947\u0932\u094d\u0925",
            "AI \u0938\u094d\u092e\u093e\u0930\u094d\u091f \u0907\u0928\u0938\u093e\u0907\u091f\u094d\u0938 \u2014 \u0939\u093f\u0902\u0926\u0940/\u0905\u0902\u0917\u094d\u0930\u0947\u091c\u093c\u0940 \u092e\u0947\u0902 \u0938\u0935\u093e\u0932 \u092a\u0942\u091b\u0947\u0902",
            "\u0924\u094d\u092f\u094b\u0939\u093e\u0930 \u0915\u0948\u0932\u0947\u0902\u0921\u0930 \u0915\u0947 \u0938\u093e\u0925 \u0938\u0940\u091c\u093c\u0928\u0932 \u090f\u0928\u093e\u0932\u093f\u0938\u093f\u0938",
        ],
        "annotations": [
            {"x": 700, "y": 300, "label": "Charts & AI", "direction": "down"},
        ],
    },
    {
        "title": "20. \u0939\u093f\u0938\u094d\u091f\u094b\u0930\u093f\u0915\u0932 \u0905\u092a\u0932\u094b\u0921 (Historical Upload)",
        "screenshot": "22_historical_upload",
        "desc": "\u092c\u0921\u093c\u0940 \u0939\u093f\u0938\u094d\u091f\u094b\u0930\u093f\u0915\u0932 Excel \u092b\u093e\u0907\u0932\u0947\u0902 (2 \u0932\u093e\u0916+ \u0930\u094b) \u0905\u092a\u0932\u094b\u0921 \u0915\u0930\u0947\u0902\u0964",
        "bullets": [
            "\u092c\u094d\u0930\u093e\u0909\u091c\u093c\u0930 \u092e\u0947\u0902 \u092a\u093e\u0930\u094d\u0938\u093f\u0902\u0917 \u2014 24MB+ \u092b\u093e\u0907\u0932\u0947\u0902 \u0938\u0902\u092d\u093e\u0932\u0924\u093e \u0939\u0948",
            "\u0930\u093f\u092f\u0932-\u091f\u093e\u0907\u092e \u092a\u094d\u0930\u094b\u0917\u094d\u0930\u0947\u0938 \u092c\u093e\u0930",
            "\u0939\u093f\u0938\u094d\u091f\u094b\u0930\u093f\u0915\u0932 \u0921\u0947\u091f\u093e \u0915\u0930\u0902\u091f \u0938\u094d\u091f\u0949\u0915 \u0915\u094b \u092a\u094d\u0930\u092d\u093e\u0935\u093f\u0924 \u0928\u0939\u0940\u0902 \u0915\u0930\u0924\u093e",
        ],
        "annotations": [
            {"x": 700, "y": 300, "label": "Upload Area", "direction": "down"},
        ],
    },
    {
        "title": "21. \u092f\u0942\u091c\u093c\u0930 \u092a\u094d\u0930\u092c\u0902\u0927\u0928 (User Management)",
        "screenshot": "19_users",
        "desc": "\u092f\u0942\u091c\u093c\u0930 \u0905\u0915\u093e\u0909\u0902\u091f \u092c\u0928\u093e\u0928\u0947 \u0914\u0930 \u092a\u094d\u0930\u092c\u0902\u0927\u093f\u0924 \u0915\u0930\u0928\u0947 \u0915\u093e \u090f\u0921\u092e\u093f\u0928 \u092a\u0948\u0928\u0932\u0964",
        "bullets": [
            "\u0935\u093f\u0936\u093f\u0937\u094d\u091f \u0930\u094b\u0932 \u0915\u0947 \u0938\u093e\u0925 \u092f\u0942\u091c\u093c\u0930 \u092c\u0928\u093e\u090f\u0902",
            "\u0905\u0915\u093e\u0909\u0902\u091f \u090f\u0915\u094d\u091f\u093f\u0935\u0947\u091f/\u0921\u093f\u090f\u0915\u094d\u091f\u093f\u0935\u0947\u091f \u0915\u0930\u0947\u0902",
            "\u092a\u093e\u0938\u0935\u0930\u094d\u0921 \u0914\u0930 \u092f\u0942\u091c\u093c\u0930\u0928\u0947\u092e \u092c\u0926\u0932\u0947\u0902",
        ],
        "annotations": [
            {"x": 500, "y": 200, "label": "User List", "direction": "right"},
            {"x": 1100, "y": 200, "label": "Actions", "direction": "left"},
        ],
    },
    {
        "title": "22. \u0939\u093f\u0938\u094d\u091f\u094d\u0930\u0940 \u0914\u0930 \u090f\u0915\u094d\u091f\u093f\u0935\u093f\u091f\u0940 \u0932\u0949\u0917 (History & Activity)",
        "screenshot": "20_history",
        "desc": "\u0938\u092d\u0940 \u0905\u092a\u0932\u094b\u0921\u094d\u0938 \u0914\u0930 \u0938\u093f\u0938\u094d\u091f\u092e \u090f\u0915\u094d\u0936\u0928\u094d\u0938 \u0915\u093e \u092a\u0942\u0930\u093e \u0911\u0921\u093f\u091f \u091f\u094d\u0930\u0947\u0932\u0964",
        "bullets": [
            "\u0905\u092a\u0932\u094b\u0921 \u0939\u093f\u0938\u094d\u091f\u094d\u0930\u0940 \u0905\u0902\u0921\u0942 \u0915\u094d\u0937\u092e\u0924\u093e \u0915\u0947 \u0938\u093e\u0925",
            "\u0939\u0930 \u090f\u0915\u094d\u0936\u0928 \u0915\u093e \u091f\u093e\u0907\u092e\u0938\u094d\u091f\u0948\u0902\u092a \u0914\u0930 \u092f\u0942\u091c\u093c\u0930 \u0907\u0928\u094d\u092b\u094b",
        ],
        "annotations": [
            {"x": 600, "y": 200, "label": "Upload History", "direction": "right"},
        ],
    },
]


def build_pdf(features, lang, output_path):
    """Build a PDF manual from feature definitions."""
    styles = get_styles(lang)
    
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=20*mm,
        rightMargin=20*mm,
        topMargin=20*mm,
        bottomMargin=20*mm,
    )
    
    story = []
    page_width = A4[0] - 40*mm  # available width
    
    # Title page
    story.append(Spacer(1, 80))
    if lang == 'en':
        story.append(Paragraph("StockBud User Manual", styles['ManualTitle']))
        story.append(Paragraph("Complete Software Guide with Screenshots", styles['ManualSubtitle']))
        story.append(Spacer(1, 20))
        story.append(Paragraph("Scope of this Software", styles['SectionTitle']))
        story.append(Spacer(1, 10))
        story.append(Paragraph(
            "StockBud is an intelligent inventory management system designed for jewelry businesses. "
            "It provides real-time stock tracking, profit analysis, seasonal ordering, "
            "physical vs book stock comparison, multi-role access control, and AI-powered insights. "
            "This manual covers all features with annotated screenshots.",
            styles['FeatureDesc']
        ))
    else:
        story.append(Paragraph("StockBud \u092f\u0942\u091c\u093c\u0930 \u092e\u0948\u0928\u094d\u092f\u0941\u0905\u0932", styles['ManualTitle']))
        story.append(Paragraph("\u0938\u094d\u0915\u094d\u0930\u0940\u0928\u0936\u0949\u091f\u094d\u0938 \u0915\u0947 \u0938\u093e\u0925 \u0938\u0902\u092a\u0942\u0930\u094d\u0923 \u0938\u0949\u092b\u094d\u091f\u0935\u0947\u092f\u0930 \u0917\u093e\u0907\u0921", styles['ManualSubtitle']))
        story.append(Spacer(1, 20))
        story.append(Paragraph("\u0907\u0938 \u0938\u0949\u092b\u094d\u091f\u0935\u0947\u092f\u0930 \u0915\u093e \u0926\u093e\u092f\u0930\u093e", styles['SectionTitle']))
        story.append(Spacer(1, 10))
        story.append(Paragraph(
            "StockBud \u090f\u0915 \u0907\u0902\u091f\u0947\u0932\u093f\u091c\u0947\u0902\u091f \u0907\u0928\u094d\u0935\u0947\u0902\u091f\u0930\u0940 \u092e\u0948\u0928\u0947\u091c\u092e\u0947\u0902\u091f \u0938\u093f\u0938\u094d\u091f\u092e \u0939\u0948 \u091c\u094b \u091c\u094d\u0935\u0947\u0932\u0930\u0940 \u092c\u093f\u091c\u093c\u0928\u0947\u0938 \u0915\u0947 \u0932\u093f\u090f \u0921\u093f\u091c\u093c\u093e\u0907\u0928 \u0915\u093f\u092f\u093e \u0917\u092f\u093e \u0939\u0948\u0964 "
            "\u092f\u0939 \u0930\u093f\u092f\u0932-\u091f\u093e\u0907\u092e \u0938\u094d\u091f\u0949\u0915 \u091f\u094d\u0930\u0948\u0915\u093f\u0902\u0917, \u0932\u093e\u092d \u0935\u093f\u0936\u094d\u0932\u0947\u0937\u0923, \u0938\u0940\u091c\u093c\u0928\u0932 \u0911\u0930\u094d\u0921\u0930\u093f\u0902\u0917, "
            "\u092b\u093f\u091c\u093c\u093f\u0915\u0932 vs \u092c\u0941\u0915 \u0938\u094d\u091f\u0949\u0915 \u0924\u0941\u0932\u0928\u093e, \u092e\u0932\u094d\u091f\u0940-\u0930\u094b\u0932 \u090f\u0915\u094d\u0938\u0947\u0938 \u0915\u0902\u091f\u094d\u0930\u094b\u0932, \u0914\u0930 AI-\u0938\u0902\u091a\u093e\u0932\u093f\u0924 \u0907\u0928\u0938\u093e\u0907\u091f\u094d\u0938 \u092a\u094d\u0930\u0926\u093e\u0928 \u0915\u0930\u0924\u093e \u0939\u0948\u0964 "
            "\u092f\u0939 \u092e\u0948\u0928\u094d\u092f\u0941\u0905\u0932 \u0938\u092d\u0940 \u092b\u0940\u091a\u0930\u094d\u0938 \u0915\u094b \u0938\u094d\u0915\u094d\u0930\u0940\u0928\u0936\u0949\u091f\u094d\u0938 \u0915\u0947 \u0938\u093e\u0925 \u0915\u0935\u0930 \u0915\u0930\u0924\u093e \u0939\u0948\u0964",
            styles['FeatureDesc']
        ))
    
    story.append(PageBreak())
    
    # Table of contents
    if lang == 'en':
        story.append(Paragraph("Table of Contents", styles['SectionTitle']))
    else:
        story.append(Paragraph("\u0935\u093f\u0937\u092f \u0938\u0942\u091a\u0940", styles['SectionTitle']))
    story.append(Spacer(1, 10))
    
    for i, feat in enumerate(features):
        story.append(Paragraph(f"{feat['title']}", styles['FeatureDesc']))
    
    story.append(PageBreak())
    
    # Feature pages
    for feat in features:
        # Title
        story.append(Paragraph(feat['title'], styles['SectionTitle']))
        story.append(Spacer(1, 4))
        
        # Description
        story.append(Paragraph(feat['desc'], styles['FeatureDesc']))
        story.append(Spacer(1, 6))
        
        # Annotated screenshot
        screenshot_path = os.path.join(SCREENSHOTS_DIR, f"{feat['screenshot']}.png")
        if os.path.exists(screenshot_path):
            # Annotate the screenshot
            annotated_path = os.path.join(SCREENSHOTS_DIR, f"{feat['screenshot']}_annotated_{lang}.png")
            annotate_screenshot(screenshot_path, feat.get('annotations', []), annotated_path)
            
            # Add to PDF - fit to page width
            img = PILImage.open(annotated_path)
            img_w, img_h = img.size
            aspect = img_h / img_w
            display_width = page_width
            display_height = display_width * aspect
            
            # Cap height to avoid overflow
            max_height = 350
            if display_height > max_height:
                display_height = max_height
                display_width = display_height / aspect
            
            img_element = Image(annotated_path, width=display_width, height=display_height)
            story.append(img_element)
            story.append(Spacer(1, 6))
        
        # Bullet points
        for bullet in feat.get('bullets', []):
            story.append(Paragraph(f"\u2022 {bullet}", styles['BulletItem']))
        
        story.append(PageBreak())
    
    # Build PDF
    doc.build(story)
    print(f"Generated: {output_path}")


if __name__ == "__main__":
    print("Generating English manual...")
    build_pdf(FEATURES_EN, 'en', os.path.join(OUTPUT_DIR, "StockBud_Manual_EN.pdf"))
    
    print("Generating Hindi manual...")
    build_pdf(FEATURES_HI, 'hi', os.path.join(OUTPUT_DIR, "StockBud_Manual_HI.pdf"))
    
    print("Done!")
