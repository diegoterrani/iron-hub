export type ServiceStatus = 'online' | 'offline' | 'unknown' | 'cli';
export type ServiceCategory =
  | 'osint'
  | 'redteam'
  | 'blue'
  | 'threat-intel'
  | 'csirt'
  | 'infra'
  | 'content'
  | 'igaming';

export interface Service {
  id: string;
  name: string;
  description: string;
  category: ServiceCategory;
  /** Public gateway path on the Hub (never a direct tool host:port). */
  gateway?: string;
  healthPath?: string;
  type: 'web' | 'api' | 'cli' | 'desktop';
  stack: string;
  project: string;
  tags: string[];
}

export function gatewayPath(id: string): string {
  // Open WebUI is a root-only SPA — nginx flips / via /go/open-webui (not /t/...).
  if (id === 'open-webui') return '/go/open-webui';
  return `/t/${id}/`;
}

export const CATEGORY_META: Record<
  ServiceCategory,
  { label: string; color: string; description: string }
> = {
  osint: {
    label: 'OSINT',
    color: '#00D9FF',
    description: 'Coleta e correlação de inteligência de fontes abertas',
  },
  'threat-intel': {
    label: 'Threat Intel',
    color: '#FF7A1A',
    description: 'Monitoramento de ameaças, dark web e IOCs',
  },
  redteam: {
    label: 'Red Team',
    color: '#FF3B45',
    description: 'Testes ofensivos autônomos e exploração autorizada',
  },
  blue: {
    label: 'Blue Team',
    color: '#2563EB',
    description: 'Defesa, detecção e resposta a incidentes',
  },
  csirt: {
    label: 'CSIRT / Forense',
    color: '#FACC15',
    description: 'Coleta forense, timeline e cadeia de custódia',
  },
  infra: {
    label: 'Infraestrutura',
    color: '#7B8190',
    description: 'Proxies, automação e serviços de suporte',
  },
  content: {
    label: 'Conteúdo',
    color: '#22C55E',
    description: 'Geração e produção de mídia',
  },
  igaming: {
    label: 'iGaming',
    color: '#4ADE80',
    description: 'Plataformas operacionais Lucky Gaming',
  },
};

export const SERVICES: Service[] = [
  {
    id: 'mosint',
    name: 'Iron OSINT',
    description: 'Email intelligence — verificação, breaches, social media, pastebin e DNS lookup.',
    category: 'osint',
    gateway: gatewayPath('mosint'),
    healthPath: '/api/health',
    type: 'web',
    stack: 'Go + React',
    project: 'mosint',
    tags: ['email', 'breach', 'hunter.io'],
  },
  {
    id: 'osint-mapping',
    name: 'Iron OSINT Mapping',
    description: 'Grafo de identificadores + mapa OSM — correlaciona handles, telefones, veículos e locais visitados (local-first).',
    category: 'osint',
    gateway: gatewayPath('osint-mapping'),
    healthPath: '/health',
    type: 'web',
    stack: 'React + Vite + Leaflet',
    project: 'OSINT-Mapping-Tool',
    tags: ['mapa', 'grafo', 'osm', 'local-first'],
  },
  {
    id: 'maverick',
    name: 'Iron MAVERICK',
    description: 'Agente de pentest autônomo — discovery de URLs, escopo e teste ofensivo com Strix.',
    category: 'redteam',
    gateway: gatewayPath('maverick'),
    healthPath: '/api/health',
    type: 'web',
    stack: 'FastAPI + React + Strix',
    project: 'Iron-maverick-agent-pentest',
    tags: ['pentest', 'strix', 'red team'],
  },
  {
    id: 'hackingbuddygpt',
    name: 'hackingBuddyGPT',
    description: 'Agentes LLM para Linux/Windows priv-esc, web/API pentest — control plane Iron + Viewer.',
    category: 'redteam',
    gateway: gatewayPath('hackingbuddygpt'),
    healthPath: '/api/health',
    type: 'web',
    stack: 'Python + FastAPI + React',
    project: 'hackingBuddyGPT',
    tags: ['llm', 'privesc', 'wintermute', 'red team'],
  },
  {
    id: 'pentestgpt',
    name: 'PentestGPT',
    description: 'Agente de pentest com LLM — Docker, jobs e providers (Claude/Codex/OpenAI).',
    category: 'redteam',
    gateway: gatewayPath('pentestgpt'),
    healthPath: '/api/health',
    type: 'web',
    stack: 'FastAPI + React + Docker',
    project: 'PentestGPT',
    tags: ['pentest', 'llm', 'docker'],
  },
  {
    id: 'scrapling',
    name: 'Scrapling',
    description: 'Scraping adaptativo anti-bot — fetch, crawl e admin Iron para OSINT/recon.',
    category: 'osint',
    gateway: gatewayPath('scrapling'),
    healthPath: '/api/health',
    type: 'web',
    stack: 'Python + FastAPI',
    project: 'Scrapling',
    tags: ['scraping', 'osint', 'recon'],
  },
  {
    id: 'pentest-ops',
    name: 'Iron Pentest Ops',
    description: 'Command center HackingTool — catálogo de ferramentas, workflow por fases e execução de pentest.',
    category: 'redteam',
    gateway: gatewayPath('pentest-ops'),
    healthPath: '/api/health',
    type: 'web',
    stack: 'React + FastAPI + HackingTool',
    project: 'hackingtool',
    tags: ['hackingtool', 'workflow', 'pentest'],
  },
  {
    id: 'burpgpt',
    name: 'Iron BurpGPT',
    description: 'Análise GPT de tráfego HTTP (req/resp/HAR) + JAR da extensão Burp Suite para passive scan com prompts customizados.',
    category: 'redteam',
    gateway: gatewayPath('burpgpt'),
    healthPath: '/api/health',
    type: 'web',
    stack: 'FastAPI + Burp Extension JAR',
    project: 'burpgpt',
    tags: ['burp', 'gpt', 'appsec', 'passive scan'],
  },
  {
    id: 'o365-csirt',
    name: 'O365 CSIRT Dashboard',
    description: 'Visualização forense de casos O365 — timeline, IOCs, MITRE ATT&CK e relatórios.',
    category: 'csirt',
    gateway: gatewayPath('o365-csirt'),
    healthPath: '/api/health',
    type: 'web',
    stack: 'FastAPI + Next.js',
    project: 'o365-csirt-collector',
    tags: ['forense', 'graph', 'timeline'],
  },
  {
    id: 'darkweb-tracker',
    name: 'DarkWeb Forums Tracker',
    description: 'Console Iron (substitui n8n) — scan de fóruns, keywords, alertas Discord/Gemini; VNC :6080 para CAPTCHA.',
    category: 'threat-intel',
    gateway: gatewayPath('darkweb-tracker'),
    healthPath: '/api/health',
    type: 'web',
    stack: 'FastAPI + SQLite + Qwen local + Playwright VNC',
    project: 'darkweb-forums-tracker',
    tags: ['dark web', 'threat intel', 'qwen', 'discord'],
  },
  {
    id: 'darkweb-observatory',
    name: 'Dark Web Observatory',
    description: 'Monitoramento de sites .onion via Tor — uptime, IOC extraction, feeds CTI e dashboard nativo.',
    category: 'threat-intel',
    gateway: gatewayPath('darkweb-observatory'),
    healthPath: '/api/health',
    type: 'web',
    stack: 'Python + Flask + Tor',
    project: 'darkweb-observatory',
    tags: ['dark web', 'onion', 'tor', 'ioc', 'cti'],
  },
  {
    id: 'robin',
    name: 'Robin OSINT',
    description: 'Investigação dark web com IA (apurvsinghgautam/robin) — Tor search/scrape + Qwen3.5-27B :8080.',
    category: 'threat-intel',
    gateway: gatewayPath('robin'),
    healthPath: '/_stcore/health',
    type: 'web',
    stack: 'Streamlit + Tor + llama.cpp',
    project: 'robin',
    tags: ['dark web', 'osint', 'llm', 'tor', 'qwen'],
  },
  {
    id: 'open-webui',
    name: 'Iron Open WebUI',
    description:
      'Chat LLM local (Qwen3.5-27B / llama.cpp :8080) em aba nova. Hub fica em /console/.',
    category: 'infra',
    gateway: '/go/open-webui',
    healthPath: '/health',
    type: 'web',
    stack: 'Open WebUI + llama.cpp',
    project: 'open-webui',
    tags: ['llm', 'qwen', '27b', 'chat', 'nginx'],
  },
  {
    id: 'moneyprinter',
    name: 'MoneyPrinterTurbo',
    description: 'Geração automatizada de vídeos curtos com IA — roteiro, voz e montagem.',
    category: 'content',
    gateway: gatewayPath('moneyprinter'),
    healthPath: '/_stcore/health',
    type: 'web',
    stack: 'Streamlit + FastAPI',
    project: 'MoneyPrinterTurbo',
    tags: ['vídeo', 'ia', 'conteúdo'],
  },
  {
    id: 'maltego-br',
    name: 'Maltego BR Transforms',
    description: 'Transforms locais para CPF, CNPJ, CEP e documentos brasileiros no Maltego 4.x.',
    category: 'osint',
    type: 'desktop',
    stack: 'Python + Maltego TRX',
    project: 'maltego-br-transforms',
    tags: ['cpf', 'cnpj', 'brasil'],
  },
  {
    id: 'websift',
    name: 'WebSift',
    description: 'Extração de emails, telefones e links de websites para OSINT ético.',
    category: 'osint',
    type: 'cli',
    stack: 'Bash + curl',
    project: 'WebSift',
    tags: ['scraping', 'email', 'cli'],
  },
  {
    id: 'bot-live',
    name: 'Bot Live Betting',
    description: 'Console operacional de apostas ao vivo — monitoramento e controle de bots.',
    category: 'igaming',
    gateway: gatewayPath('bot-live'),
    healthPath: '/api/health',
    type: 'web',
    stack: 'Node.js + Express',
    project: 'BotLiveBetting',
    tags: ['betting', 'live'],
  },
  {
    id: 'onboarding',
    name: 'Onboarding Casas',
    description: 'Fluxo de onboarding para novas casas de apostas na plataforma.',
    category: 'igaming',
    gateway: gatewayPath('onboarding'),
    healthPath: '/',
    type: 'web',
    stack: 'Node.js',
    project: 'lucky-gaming',
    tags: ['onboarding', 'casas'],
  },
  {
    id: 'casino-bot',
    name: 'Casino Bot Lab',
    description:
      'Telegram casino (aiogram) em modo lab — status, polling e SQLite. Pagamentos reais desligados.',
    category: 'igaming',
    gateway: gatewayPath('casino-bot'),
    healthPath: '/api/health',
    type: 'web',
    stack: 'Python + aiogram 2 + Docker',
    project: 'Casino_bot',
    tags: ['telegram', 'casino', 'lab', 'aiogram'],
  },
  {
    id: 'betbonus',
    name: 'Casino Integrity',
    description:
      'Console SOC dos agentes de cassino — operação, execução e admin nas 3 casas (sessão, jogos, timers, promo, saque).',
    category: 'igaming',
    gateway: gatewayPath('betbonus'),
    healthPath: '/api/health',
    type: 'web',
    stack: 'FastAPI + React',
    project: 'BetBonusAI',
    tags: ['casino', 'integrity', 'agentes', 'bonus', 'red team', 'lucky'],
  },
  {
    id: 'cdn-image',
    name: 'CDN Image Debug',
    description:
      'Scrape de endpoints de imagem + throttle 3G/4G/5G/alta para detectar falhas Akamai/CDN.',
    category: 'infra',
    gateway: gatewayPath('cdn-image'),
    healthPath: '/api/health',
    type: 'web',
    stack: 'FastAPI + Iron UI',
    project: 'cdn-image-debug',
    tags: ['akamai', 'cdn', 'imagens', 'throttle', 'performance'],
  },
  {
    id: 'graphify',
    name: 'Graphify MCP',
    description:
      'Knowledge graph do Iron Tools — query/path/explain via MCP Streamable HTTP (proxy Hub/nginx).',
    category: 'infra',
    gateway: gatewayPath('graphify'),
    healthPath: '/mcp',
    type: 'api',
    stack: 'graphifyy + MCP HTTP',
    project: 'graphify',
    tags: ['mcp', 'knowledge-graph', 'ast', 'llm'],
  },
];
