import { useEffect, useState } from 'react';
import axios from 'axios';
import { Package, TrendingUp, AlertTriangle, CheckCircle2, Clock, Globe } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [stampHistory, setStampHistory] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStats();
    fetchStampHistory();
  }, []);

  const fetchStats = async () => {
    try {
      const response = await axios.get(`${API}/stats`);
      setStats(response.data);
    } catch (error) {
      console.error('Error fetching stats:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchStampHistory = async () => {
    try {
      const response = await axios.get(`${API}/stamp-verification/history`);
      setStampHistory(response.data);
    } catch (error) {
      console.error('Error fetching stamp history:', error);
    }
  };

  const getDaysSinceVerification = (lastDate) => {
    if (!lastDate) return 999;
    const last = new Date(lastDate);
    const now = new Date();
    return Math.floor((now - last) / (1000 * 60 * 60 * 24));
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-muted-foreground">Loading...</div>
      </div>
    );
  }

  const statCards = [
    {
      title: 'Total Transactions',
      value: stats?.total_transactions || 0,
      icon: Package,
      color: 'text-primary',
      bgColor: 'bg-primary/10',
    },
    {
      title: 'Total Parties',
      value: stats?.total_parties || 0,
      icon: TrendingUp,
      color: 'text-accent',
      bgColor: 'bg-accent/10',
    },
    {
      title: 'Purchases',
      value: stats?.total_purchases || 0,
      icon: TrendingUp,
      color: 'text-secondary',
      bgColor: 'bg-secondary/10',
    },
    {
      title: 'Sales',
      value: stats?.total_sales || 0,
      icon: TrendingUp,
      color: 'text-accent',
      bgColor: 'bg-accent/10',
    },
  ];

  return (
    <div className="p-3 sm:p-6 md:p-8 space-y-6" data-testid="dashboard-page">
      <div>
        <h1 className="text-2xl sm:text-4xl md:text-5xl font-bold tracking-tight" data-testid="dashboard-title">
          Dashboard
        </h1>
        <p className="text-xs sm:text-base md:text-lg text-muted-foreground mt-2">
          StockBud - Intelligent inventory management for your jewelry business
        </p>
      </div>

      {/* Latest Match Alert */}
      {stats?.latest_match && (
        <Alert
          data-testid="latest-match-alert"
          className={`${
            stats.latest_match.complete_match
              ? 'border-accent/30 bg-accent/10'
              : 'border-secondary/30 bg-secondary/10'
          }`}
        >
          {stats.latest_match.complete_match ? (
            <CheckCircle2 className="h-5 w-5 text-accent" />
          ) : (
            <AlertTriangle className="h-5 w-5 text-secondary" />
          )}
          <AlertDescription className="ml-2">
            {stats.latest_match.complete_match
              ? '🎉 Complete stock match achieved!'
              : `Last match found ${stats.latest_match.differences?.length || 0} differences and ${stats.latest_match.unmatched_items?.length || 0} unmatched items`}
          </AlertDescription>
        </Alert>
      )}

      {/* Stats Grid */}
      <div className="grid gap-3 sm:gap-6 grid-cols-2 md:grid-cols-2 lg:grid-cols-4">
        {statCards.map((stat) => (
          <Card
            key={stat.title}
            className="stat-card relative overflow-hidden border-border/40 shadow-sm hover:shadow-md transition-shadow"
            data-testid={`stat-card-${stat.title.toLowerCase().replace(' ', '-')}`}
          >
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {stat.title}
              </CardTitle>
              <div className={`stat-card-icon p-2 rounded-lg ${stat.bgColor}`}>
                <stat.icon className={`h-5 w-5 ${stat.color}`} />
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-lg sm:text-2xl md:text-3xl font-bold font-mono">{stat.value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Stamp Verification Status */}
      <Card className="border-border/40 shadow-sm">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-5 w-5 text-primary" />
            Stamp Verification Status
          </CardTitle>
          <CardDescription>Last physical verification for each stamp</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto max-h-96">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Stamp</TableHead>
                  <TableHead>Last Verified</TableHead>
                  <TableHead>Days Ago</TableHead>
                  <TableHead className="text-right">Difference</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {stampHistory.map((stamp, idx) => {
                  const daysAgo = getDaysSinceVerification(stamp.last_verified_date);
                  const isOverdue = daysAgo > 15;
                  
                  return (
                    <TableRow key={idx} className={isOverdue ? 'bg-red-50 border-l-4 border-red-500' : ''}>
                      <TableCell className="font-bold">{stamp.stamp}</TableCell>
                      <TableCell className="text-sm">
                        {stamp.last_verified_date ? new Date(stamp.last_verified_date).toLocaleDateString() : 'Never'}
                      </TableCell>
                      <TableCell>
                        <Badge variant={isOverdue ? 'destructive' : 'outline'}>
                          {daysAgo === 999 ? 'Never' : `${daysAgo} days`}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right font-mono">
                        {stamp.difference ? `${stamp.difference >= 0 ? '+' : ''}${stamp.difference.toFixed(3)} kg` : '-'}
                      </TableCell>
                      <TableCell>
                        {isOverdue ? (
                          <Badge className="bg-red-600">
                            <AlertTriangle className="h-3 w-3 mr-1" />
                            Needs Verification
                          </Badge>
                        ) : stamp.is_match ? (
                          <Badge className="bg-green-600">
                            <CheckCircle2 className="h-3 w-3 mr-1" />
                            Matched
                          </Badge>
                        ) : (
                          <Badge variant="outline">Unknown</Badge>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Software Scope — Bilingual */}
      <ScopeSection />
    </div>
  );
}

const SCOPE_EN = [
  { title: 'Inventory Management', items: [
    'Upload opening stock, purchase ledgers, and sale ledgers from Excel files',
    'Automatic "Book Inventory" calculation: Opening Stock + Purchases − Sales',
    'Current Stock page shows real-time inventory for every item with stamp-wise grouping',
    'Negative stock detection — highlights items with naming inconsistencies',
    'Physical vs Book comparison — upload physical stock and compare against calculated book stock',
    'Stamp-wise verification tracking with overdue alerts (>15 days)',
  ]},
  { title: 'Item Mapping & Grouping', items: [
    'Map transaction names to master item names (e.g., "JB-70 KADA CC" → "JB-70 KADA II")',
    'Item Groups — merge interchangeable items (e.g., "SNT 40 Premium" + "SNT 40") so their stock and sales are combined',
    'Group leader appears everywhere (Current Stock, Buffers, Orders) with consolidated numbers',
    'Auto-detect groupable items from existing mappings',
  ]},
  { title: 'Historical Data Upload (Large Files)', items: [
    'Upload historical sale/purchase Excel files up to 200K+ rows (24MB+)',
    'Client-side parsing — file is processed in your browser, sent in small batches; server never runs out of memory',
    'Progress bar shows real-time batch status during upload',
    'Historical data is kept separate — it does NOT affect your current stock or dashboard',
  ]},
  { title: 'Profit Analysis', items: [
    'Silver Profit (kg) = difference in tunch (purity) between purchase and sale',
    'Labour Profit (₹) = difference in labour charges per gram between sale and purchase',
    'Views: Customer-wise, Supplier-wise, Item-wise, Month-wise, Yearly summary',
    'Uses purchase rates from the Purchase Ledger as the cost basis',
    'Historical Profit — analyzes uploaded historical data across multiple years',
  ]},
  { title: 'Item Buffers & Seasonal Ordering', items: [
    'Auto-categorizes every item into tiers: Fastest, Fast, Medium, Slow, Dead',
    'Velocity calculated from BOTH current + historical sales data (averaged over years)',
    'Indian festival season awareness — Diwali, Akshaya Tritiya, Wedding Season, Holi, Karva Chauth, Sankranti',
    'Season boost multiplier applied to buffers during peak periods (up to 1.5× during Diwali)',
    'Minimum stock, lower buffer, upper buffer calculated per tier with seasonal adjustment',
    'Red/Green/Yellow status: Below minimum → Red, Healthy → Green, Overstocked → Yellow',
  ]},
  { title: 'Order Management', items: [
    'Stock deficit alerts with one-click "Quick Order" from notifications',
    'Suggested order quantity range based on buffer calculations',
    'Track order status: Ordered → Received, with overdue alerts (7+ days)',
    'Overdue orders highlighted in red for immediate attention',
  ]},
  { title: 'Stamp Management & Assignment', items: [
    'Stamps represent physical trays/sections in your warehouse',
    'Click any stamp to see all items in it, total stock, and assigned executive',
    'Assign one Sales Entry Executive per stamp — executive can only enter stock for their assigned stamps',
    'Normalize stamp names (STAMP 1, STAMP 2, etc.) across all collections',
  ]},
  { title: 'Party Analytics', items: [
    'Customer-wise and Supplier-wise transaction breakdown',
    'Total weight traded, number of transactions, average rates per party',
    'Identifies top customers and suppliers by volume',
  ]},
  { title: 'AI-Powered Insights', items: [
    'Smart Insights — ask questions about your data in natural language, get AI analysis',
    'Seasonal Analysis — AI recommends which items to stock up for upcoming festivals',
    'Uses Claude AI (Anthropic) via Emergent LLM integration',
    'Data-driven recommendations even when AI budget is exceeded',
  ]},
  { title: 'User Roles & Security', items: [
    'Admin — full access: upload files, manage users, view analytics, configure buffers',
    'Manager — approval workflows, physical vs book verification',
    'Sales Executive — stock entry for assigned stamps only',
    'Polythene Executive — polythene weight adjustments only',
    'JWT authentication with 18-hour token expiry',
  ]},
  { title: 'Data Visualization', items: [
    'Sales trends, purchase trends, inventory health charts',
    'Profit tab with historical profit breakdown',
    'Seasonal analysis with festival calendar overlay',
    'CSV export available on all data tables',
  ]},
];

const SCOPE_HI = [
  { title: 'इन्वेंटरी प्रबंधन', items: [
    'Excel फाइलों से ओपनिंग स्टॉक, खरीद लेजर और बिक्री लेजर अपलोड करें',
    'स्वचालित "बुक इन्वेंटरी" गणना: ओपनिंग स्टॉक + खरीद − बिक्री',
    'करंट स्टॉक पेज — हर आइटम की रियल-टाइम इन्वेंटरी स्टैम्प-वाइज ग्रुपिंग के साथ',
    'नेगेटिव स्टॉक डिटेक्शन — नामकरण की गड़बड़ी वाले आइटम हाइलाइट होते हैं',
    'फिजिकल vs बुक तुलना — फिजिकल स्टॉक अपलोड करें और बुक स्टॉक से तुलना करें',
    'स्टैम्प-वाइज वेरिफिकेशन ट्रैकिंग, 15 दिन से ज्यादा पुराने की अलर्ट',
  ]},
  { title: 'आइटम मैपिंग और ग्रुपिंग', items: [
    'ट्रांजैक्शन नामों को मास्टर आइटम नामों से मैप करें (जैसे "JB-70 KADA CC" → "JB-70 KADA II")',
    'आइटम ग्रुप्स — एक जैसे आइटम मर्ज करें (जैसे "SNT 40 Premium" + "SNT 40") ताकि उनका स्टॉक और बिक्री एक साथ दिखे',
    'ग्रुप लीडर हर जगह दिखाई देता है (करंट स्टॉक, बफर्स, ऑर्डर्स) संयुक्त नंबरों के साथ',
    'मौजूदा मैपिंग से ग्रुपेबल आइटम अपने आप पहचाने जाते हैं',
  ]},
  { title: 'हिस्टोरिकल डेटा अपलोड (बड़ी फाइलें)', items: [
    '2 लाख+ रो (24MB+) की हिस्टोरिकल बिक्री/खरीद Excel फाइलें अपलोड करें',
    'ब्राउज़र में ही पार्सिंग — फाइल आपके ब्राउज़र में प्रोसेस होती है, छोटे बैच में भेजी जाती है; सर्वर की मेमोरी कभी खत्म नहीं होती',
    'अपलोड के दौरान रियल-टाइम प्रोग्रेस बार',
    'हिस्टोरिकल डेटा अलग रखा जाता है — यह आपके करंट स्टॉक या डैशबोर्ड को प्रभावित नहीं करता',
  ]},
  { title: 'लाभ विश्लेषण (Profit Analysis)', items: [
    'सिल्वर प्रॉफिट (kg) = खरीद और बिक्री के बीच टंच (शुद्धता) का अंतर',
    'लेबर प्रॉफिट (₹) = बिक्री और खरीद के बीच प्रति ग्राम लेबर चार्ज का अंतर',
    'व्यू: ग्राहक-वाइज, सप्लायर-वाइज, आइटम-वाइज, महीना-वाइज, वार्षिक सारांश',
    'खरीद लेजर की दरों को लागत आधार (cost basis) के रूप में उपयोग करता है',
    'हिस्टोरिकल प्रॉफिट — कई सालों के अपलोड किए गए हिस्टोरिकल डेटा का विश्लेषण',
  ]},
  { title: 'आइटम बफर और सीज़नल ऑर्डरिंग', items: [
    'हर आइटम को अपने आप टियर में बांटता है: सबसे तेज़, तेज़, मध्यम, धीमा, बंद (Dead)',
    'वेलोसिटी की गणना करंट + हिस्टोरिकल बिक्री डेटा दोनों से (सालों का औसत)',
    'भारतीय त्योहार सीज़न की पहचान — दिवाली, अक्षय तृतीया, शादी का सीज़न, होली, करवा चौथ, संक्रांति',
    'त्योहारी सीज़न में बफर पर बूस्ट मल्टीप्लायर (दिवाली में 1.5× तक)',
    'मिनिमम स्टॉक, लोअर बफर, अपर बफर — हर टियर के लिए सीज़नल एडजस्टमेंट के साथ',
    'लाल/हरा/पीला स्टेटस: मिनिमम से कम → लाल, स्वस्थ → हरा, ज्यादा स्टॉक → पीला',
  ]},
  { title: 'ऑर्डर प्रबंधन', items: [
    'स्टॉक कमी की अलर्ट के साथ एक-क्लिक "क्विक ऑर्डर"',
    'बफर गणना के आधार पर सुझाई गई ऑर्डर मात्रा',
    'ऑर्डर स्टेटस ट्रैक करें: ऑर्डर किया → प्राप्त हुआ, 7+ दिन की ओवरड्यू अलर्ट',
    'ओवरड्यू ऑर्डर लाल रंग में हाइलाइट',
  ]},
  { title: 'स्टैम्प प्रबंधन और असाइनमेंट', items: [
    'स्टैम्प = आपके गोदाम में फिजिकल ट्रे/सेक्शन',
    'किसी भी स्टैम्प पर क्लिक करें — उसमें सभी आइटम, कुल स्टॉक, और असाइन एक्जीक्यूटिव दिखेगा',
    'एक स्टैम्प पर एक सेल्स एक्जीक्यूटिव — वह सिर्फ अपने असाइन स्टैम्प का स्टॉक एंट्री कर सकता है',
    'सभी कलेक्शन में स्टैम्प नाम नॉर्मलाइज़ करें (STAMP 1, STAMP 2, आदि)',
  ]},
  { title: 'पार्टी एनालिटिक्स', items: [
    'ग्राहक-वाइज और सप्लायर-वाइज ट्रांजैक्शन ब्रेकडाउन',
    'प्रति पार्टी कुल वजन, ट्रांजैक्शन की संख्या, औसत दरें',
    'वॉल्यूम के आधार पर टॉप ग्राहक और सप्लायर की पहचान',
  ]},
  { title: 'AI-संचालित इनसाइट्स', items: [
    'स्मार्ट इनसाइट्स — अपने डेटा के बारे में हिंदी/अंग्रेज़ी में सवाल पूछें, AI विश्लेषण पाएं',
    'सीज़नल एनालिसिस — AI बताता है कि आगामी त्योहारों के लिए कौन से आइटम स्टॉक करें',
    'Emergent LLM इंटीग्रेशन के ज़रिए Claude AI (Anthropic) का उपयोग',
    'AI बजट खत्म होने पर भी डेटा-आधारित सिफारिशें मिलती हैं',
  ]},
  { title: 'यूज़र रोल और सुरक्षा', items: [
    'एडमिन — पूरा एक्सेस: फाइल अपलोड, यूज़र प्रबंधन, एनालिटिक्स, बफर कॉन्फ़िग',
    'मैनेजर — अप्रूवल वर्कफ़्लो, फिजिकल vs बुक वेरिफिकेशन',
    'सेल्स एक्जीक्यूटिव — सिर्फ असाइन स्टैम्प के लिए स्टॉक एंट्री',
    'पॉलीथीन एक्जीक्यूटिव — सिर्फ पॉलीथीन वजन एडजस्टमेंट',
    'JWT ऑथेंटिकेशन, 18 घंटे की टोकन एक्सपायरी',
  ]},
  { title: 'डेटा विज़ुअलाइज़ेशन', items: [
    'बिक्री ट्रेंड, खरीद ट्रेंड, इन्वेंटरी हेल्थ चार्ट',
    'प्रॉफिट टैब में हिस्टोरिकल प्रॉफिट ब्रेकडाउन',
    'त्योहार कैलेंडर ओवरले के साथ सीज़नल एनालिसिस',
    'सभी डेटा टेबल पर CSV एक्सपोर्ट उपलब्ध',
  ]},
];

function ScopeSection() {
  const [lang, setLang] = useState('en');
  const scope = lang === 'en' ? SCOPE_EN : SCOPE_HI;

  return (
    <Card className="border-border/40 shadow-sm" data-testid="scope-section">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-xl">{lang === 'en' ? 'Software Capabilities' : 'सॉफ्टवेयर की क्षमताएं'}</CardTitle>
            <CardDescription>{lang === 'en' ? 'Complete scope of what StockBud can do' : 'StockBud क्या-क्या कर सकता है — पूरा विवरण'}</CardDescription>
          </div>
          <Button variant="outline" size="sm" onClick={() => setLang(l => l === 'en' ? 'hi' : 'en')}
            data-testid="lang-toggle" className="gap-1.5">
            <Globe className="h-4 w-4" />
            {lang === 'en' ? 'हिंदी' : 'English'}
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid gap-4 md:grid-cols-2">
          {scope.map((section, idx) => (
            <div key={idx} className="rounded-lg border border-border/40 p-4 space-y-2">
              <h3 className="font-semibold text-sm text-primary">{section.title}</h3>
              <ul className="space-y-1">
                {section.items.map((item, i) => (
                  <li key={i} className="text-xs text-muted-foreground leading-relaxed flex gap-1.5">
                    <span className="text-primary/60 mt-0.5 shrink-0">&#x2022;</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}