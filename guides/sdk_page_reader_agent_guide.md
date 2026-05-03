# SDK Page Reader: Полное руководство для ИИ-агента

## Руководство по внедрению и использованию для парсинга веб-страниц

---

## Содержание

1. [Обзор и возможности](#1-обзор-и-возможности)
2. [Установка и подготовка](#2-установка-и-подготовка)
3. [Базовое использование](#3-базовое-использование)
4. [Продвинутые техники](#4-продвинутые-техники)
5. [Парсинг JSprav.ru](#5-парсинг-jspravru)
6. [Обработка ошибок](#6-обработка-ошибок)
7. [Оптимизация и кэширование](#7-оптимизация-и-кэширование)
8. [Примеры для типовых задач](#8-примеры-для-типовых-задач)
9. [Чек-лист для ИИ-агента](#9-чек-лист-для-ии-агента)

---

## 1. Обзор и возможности

### Что такое SDK Page Reader?

SDK Page Reader — это готовый API для извлечения контента с веб-страниц. Он автоматически:
- Загружает страницу
- Рендерит JavaScript (SPA, динамический контент)
- Извлекает основной контент
- Возвращает структурированные данные

### Ключевые преимущества для ИИ-агента

| Преимущество | Описание |
|--------------|----------|
| **Без настройки** | Не нужно устанавливать браузер, драйверы, зависимости |
| **JS-рендеринг** | Автоматически выполняет JavaScript на странице |
| **Готовый результат** | Возвращает HTML, текст, метаданные |
| **Простое API** | Один вызов функции — минимум кода |
| **Backend-only** | Работает на сервере, безопасно для credentials |

### Что возвращает Page Reader

```typescript
interface PageReaderResult {
  code: number;           // HTTP код ответа
  status: number;         // Статус операции
  data: {
    title: string;        // Заголовок страницы
    html: string;         // HTML контент (основной)
    text: string;         // Текстовое содержимое
    url: string;          // Финальный URL (после редиректов)
    publishedTime: string; // Дата публикации (если найдена)
    metadata: object;     // Дополнительные метаданные
    usage: {
      tokens: number;     // Использовано токенов
    };
  };
}
```

---

## 2. Установка и подготовка

### Шаг 1: Проверка установки SDK

SDK уже установлен в проекте. Проверьте наличие пакета:

```bash
# Проверка установки
npm list z-ai-web-dev-sdk

# Если не установлен:
npm install z-ai-web-dev-sdk
```

### Шаг 2: Структура проекта

```
your-project/
├── src/
│   ├── scrapers/
│   │   └── jsprav-scraper.ts    # Ваш скрапер
│   └── agents/
│       └── parsing-agent.ts     # ИИ-агент
├── package.json
└── node_modules/
    └── z-ai-web-dev-sdk/        # SDK
```

### Шаг 3: Импорт и инициализация

```typescript
// ES Module (рекомендуется)
import ZAI from 'z-ai-web-dev-sdk';

// CommonJS
const ZAI = require('z-ai-web-dev-sdk').default;
```

---

## 3. Базовое использование

### Минимальный пример

```typescript
import ZAI from 'z-ai-web-dev-sdk';

async function readPage(url: string) {
  // Создаём экземпляр SDK
  const zai = await ZAI.create();
  
  // Вызываем page_reader
  const result = await zai.functions.invoke('page_reader', {
    url: url
  });
  
  return result;
}

// Использование
const page = await readPage('https://example.com');
console.log('Заголовок:', page.data.title);
console.log('Контент:', page.data.html);
```

### Получение текста страницы

```typescript
import ZAI from 'z-ai-web-dev-sdk';

async function getPageText(url: string): Promise<string> {
  const zai = await ZAI.create();
  
  const result = await zai.functions.invoke('page_reader', {
    url: url
  });
  
  // Вариант 1: Использовать готовое текстовое поле
  if (result.data.text) {
    return result.data.text;
  }
  
  // Вариант 2: Конвертировать HTML в текст
  const html = result.data.html;
  const text = html
    .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, '')
    .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, '')
    .replace(/<[^>]*>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  
  return text;
}
```

### Получение HTML и извлечение данных

```typescript
import ZAI from 'z-ai-web-dev-sdk';

interface CompanyData {
  name: string | null;
  address: string | null;
  phone: string | null;
  email: string | null;
}

async function extractCompanyData(url: string): Promise<CompanyData> {
  const zai = await ZAI.create();
  
  const result = await zai.functions.invoke('page_reader', {
    url: url
  });
  
  const html = result.data.html;
  
  // Извлечение данных с помощью регулярных выражений
  // (для production лучше использовать cheerio или jsdom)
  
  const nameMatch = html.match(/<h1[^>]*class="[^"]*company-name[^"]*"[^>]*>(.*?)<\/h1>/i);
  const addressMatch = html.match(/<div[^>]*class="[^"]*address[^"]*"[^>]*>(.*?)<\/div>/i);
  const phoneMatch = html.match(/tel:([+0-9\s\-\(\)]+)/i);
  const emailMatch = html.match(/([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/i);
  
  return {
    name: nameMatch ? nameMatch[1].trim() : null,
    address: addressMatch ? addressMatch[1].trim() : null,
    phone: phoneMatch ? phoneMatch[1].trim() : null,
    email: emailMatch ? emailMatch[1].trim() : null,
  };
}
```

---

## 4. Продвинутые техники

### Класс для работы с Page Reader

```typescript
import ZAI from 'z-ai-web-dev-sdk';

interface PageData {
  url: string;
  title: string;
  html: string;
  text: string;
  publishedTime?: string;
  fetchedAt: string;
}

class PageReaderService {
  private zai: Awaited<ReturnType<typeof ZAI.create>> | null = null;
  private cache: Map<string, { data: PageData; timestamp: number }> = new Map();
  private cacheDuration: number = 3600000; // 1 час
  
  /**
   * Инициализация SDK
   */
  async init(): Promise<void> {
    if (!this.zai) {
      this.zai = await ZAI.create();
    }
  }
  
  /**
   * Проверка инициализации
   */
  private ensureInitialized(): void {
    if (!this.zai) {
      throw new Error('PageReaderService not initialized. Call init() first.');
    }
  }
  
  /**
   * Чтение страницы с кэшированием
   */
  async readPage(url: string, useCache: boolean = true): Promise<PageData> {
    this.ensureInitialized();
    
    // Проверка кэша
    if (useCache) {
      const cached = this.cache.get(url);
      if (cached && Date.now() - cached.timestamp < this.cacheDuration) {
        console.log(`[Cache] Returning cached data for: ${url}`);
        return cached.data;
      }
    }
    
    // Загрузка страницы
    const result = await this.zai!.functions.invoke('page_reader', {
      url: url
    });
    
    // Формирование результата
    const pageData: PageData = {
      url: result.data.url,
      title: result.data.title || '',
      html: result.data.html || '',
      text: result.data.text || '',
      publishedTime: result.data.publishedTime,
      fetchedAt: new Date().toISOString(),
    };
    
    // Сохранение в кэш
    this.cache.set(url, {
      data: pageData,
      timestamp: Date.now(),
    });
    
    return pageData;
  }
  
  /**
   * Чтение нескольких страниц параллельно
   */
  async readPages(urls: string[], concurrency: number = 3): Promise<PageData[]> {
    const results: PageData[] = [];
    
    // Обработка батчами
    for (let i = 0; i < urls.length; i += concurrency) {
      const batch = urls.slice(i, i + concurrency);
      
      const batchResults = await Promise.allSettled(
        batch.map(url => this.readPage(url))
      );
      
      for (const result of batchResults) {
        if (result.status === 'fulfilled') {
          results.push(result.value);
        } else {
          console.error(`Failed to read page: ${result.reason}`);
        }
      }
      
      console.log(`Processed batch ${Math.floor(i / concurrency) + 1}/${Math.ceil(urls.length / concurrency)}`);
    }
    
    return results;
  }
  
  /**
   * Очистка кэша
   */
  clearCache(): void {
    this.cache.clear();
  }
  
  /**
   * Получение статистики кэша
   */
  getCacheStats(): { size: number; urls: string[] } {
    return {
      size: this.cache.size,
      urls: Array.from(this.cache.keys()),
    };
  }
}

// Использование
const pageReader = new PageReaderService();
await pageReader.init();

const page = await pageReader.readPage('https://example.com');
console.log(page.title);
```

### Обёртка с обработкой ошибок и retry

```typescript
import ZAI from 'z-ai-web-dev-sdk';

interface RetryOptions {
  maxRetries: number;
  delayMs: number;
  backoffMultiplier: number;
}

const DEFAULT_RETRY_OPTIONS: RetryOptions = {
  maxRetries: 3,
  delayMs: 1000,
  backoffMultiplier: 2,
};

async function readPageWithRetry(
  url: string,
  options: Partial<RetryOptions> = {}
): Promise<{
  success: boolean;
  data?: any;
  error?: string;
  attempts: number;
}> {
  const opts = { ...DEFAULT_RETRY_OPTIONS, ...options };
  const zai = await ZAI.create();
  
  let lastError: string = '';
  let delay = opts.delayMs;
  
  for (let attempt = 1; attempt <= opts.maxRetries; attempt++) {
    try {
      console.log(`[Attempt ${attempt}/${opts.maxRetries}] Reading: ${url}`);
      
      const result = await zai.functions.invoke('page_reader', {
        url: url
      });
      
      // Проверка успешности
      if (result.code === 200 && result.data?.html) {
        return {
          success: true,
          data: result.data,
          attempts: attempt,
        };
      }
      
      // Если код не 200
      lastError = `HTTP ${result.code || 'unknown'}`;
      
    } catch (error: any) {
      lastError = error.message || 'Unknown error';
      console.error(`[Attempt ${attempt}] Error: ${lastError}`);
    }
    
    // Задержка перед следующей попыткой (кроме последней)
    if (attempt < opts.maxRetries) {
      console.log(`Waiting ${delay}ms before retry...`);
      await new Promise(resolve => setTimeout(resolve, delay));
      delay *= opts.backoffMultiplier;
    }
  }
  
  return {
    success: false,
    error: lastError,
    attempts: opts.maxRetries,
  };
}

// Использование
const result = await readPageWithRetry('https://example.com', {
  maxRetries: 5,
  delayMs: 500,
});

if (result.success) {
  console.log('Page loaded:', result.data.title);
} else {
  console.error('Failed after', result.attempts, 'attempts:', result.error);
}
```

---

## 5. Парсинг JSprav.ru

### Полный скрапер для JSprav.ru

```typescript
import ZAI from 'z-ai-web-dev-sdk';

// Типы данных
interface JSpravCompany {
  name: string;
  address: string;
  phone: string;
  email: string | null;
  website: string | null;
  category: string;
  city: string;
  rating: number | null;
  reviewsCount: number | null;
  sourceUrl: string;
  parsedAt: string;
}

interface JSpravScraperConfig {
  city: string;
  categories: string[];
  maxPagesPerCategory: number;
  delayBetweenRequests: number;
}

class JSpravScraper {
  private zai: Awaited<ReturnType<typeof ZAI.create>> | null = null;
  private results: JSpravCompany[] = [];
  
  /**
   * Инициализация
   */
  async init(): Promise<void> {
    this.zai = await ZAI.create();
    console.log('✓ JSpravScraper initialized');
  }
  
  /**
   * Получение URL поддомена города
   */
  private getCityUrl(city: string): string {
    // Маппинг названий городов к поддоменам
    const cityMap: Record<string, string> = {
      'москва': 'moskva1',
      'moscow': 'moskva1',
      'санкт-петербург': 'sankt-peterburg1',
      'spb': 'sankt-peterburg1',
      'новосибирск': 'novosibirsk',
      'екатеринбург': 'ekaterinburg',
      'казань': 'kazan',
      'нижний новгород': 'nizhnij-novgorod',
      'челябинск': 'chelyabinsk',
      'самара': 'samara',
      'омск': 'omsk',
      'ростов-на-дону': 'rostov-na-donu',
      'уфа': 'ufa',
      'красноярск': 'krasnoyarsk',
      'воронеж': 'voronezh',
      'пермь': 'perm',
      'волгоград': 'volgograd',
    };
    
    const subdomain = cityMap[city.toLowerCase()] || city.toLowerCase();
    return `https://${subdomain}.jsprav.ru`;
  }
  
  /**
   * Чтение страницы
   */
  private async fetchPage(url: string): Promise<string> {
    if (!this.zai) {
      throw new Error('Scraper not initialized');
    }
    
    const result = await this.zai.functions.invoke('page_reader', {
      url: url
    });
    
    if (result.code !== 200 || !result.data?.html) {
      throw new Error(`Failed to fetch page: ${result.code}`);
    }
    
    return result.data.html;
  }
  
  /**
   * Извлечение компаний из HTML категории
   */
  private parseCategoryPage(html: string, city: string, category: string): Partial<JSpravCompany>[] {
    const companies: Partial<JSpravCompany>[] = [];
    
    // Регулярные выражения для извлечения данных
    // Примечание: селекторы нужно адаптировать под реальную структуру сайта
    
    // Поиск элементов компаний
    const companyPattern = /<div[^>]*class="[^"]*company-item[^"]*"[^>]*>([\s\S]*?)<\/div>\s*(?=<div[^>]*class="[^"]*company-item|<\/div>\s*<\/div>)/gi;
    
    let match;
    while ((match = companyPattern.exec(html)) !== null) {
      const companyHtml = match[1];
      
      // Извлечение названия
      const nameMatch = companyHtml.match(/<a[^>]*class="[^"]*company-name[^"]*"[^>]*>(.*?)<\/a>/i);
      const name = nameMatch ? this.cleanText(nameMatch[1]) : '';
      
      // Извлечение адреса
      const addressMatch = companyHtml.match(/<div[^>]*class="[^"]*address[^"]*"[^>]*>(.*?)<\/div>/i);
      const address = addressMatch ? this.cleanText(addressMatch[1]) : '';
      
      // Извлечение телефона
      const phoneMatch = companyHtml.match(/tel:([+0-9\s\-\(\)]+)/i);
      const phone = phoneMatch ? phoneMatch[1].trim() : '';
      
      // Извлечение ссылки
      const linkMatch = companyHtml.match(/<a[^>]*href="([^"]*)"[^>]*class="[^"]*company-name/i);
      const link = linkMatch ? linkMatch[1] : '';
      
      if (name) {
        companies.push({
          name,
          address,
          phone,
          category,
          city,
          sourceUrl: link,
          parsedAt: new Date().toISOString(),
        });
      }
    }
    
    return companies;
  }
  
  /**
   * Извлечение детальной информации со страницы компании
   */
  private async enrichCompanyData(basicData: Partial<JSpravCompany>): Promise<JSpravCompany> {
    if (!basicData.sourceUrl?.startsWith('http')) {
      return this.asCompany(basicData);
    }
    
    try {
      const html = await this.fetchPage(basicData.sourceUrl);
      
      // Извлечение email
      const emailMatch = html.match(/([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/i);
      basicData.email = emailMatch ? emailMatch[1] : null;
      
      // Извлечение сайта
      const websiteMatch = html.match(/<a[^>]*href="(https?:\/\/[^"]*)"[^>]*>(?:сайт|website|www)/i);
      basicData.website = websiteMatch ? websiteMatch[1] : null;
      
      // Извлечение рейтинга
      const ratingMatch = html.match(/rating["\s:]+(\d+[.,]\d)/i);
      basicData.rating = ratingMatch ? parseFloat(ratingMatch[1].replace(',', '.')) : null;
      
      // Извлечение количества отзывов
      const reviewsMatch = html.match(/(\d+)\s*(отзыв|review)/i);
      basicData.reviewsCount = reviewsMatch ? parseInt(reviewsMatch[1]) : null;
      
    } catch (error) {
      console.error(`Failed to enrich company ${basicData.name}:`, error);
    }
    
    return this.asCompany(basicData);
  }
  
  /**
   * Очистка текста от HTML-тегов
   */
  private cleanText(html: string): string {
    return html
      .replace(/<[^>]*>/g, '')
      .replace(/&nbsp;/g, ' ')
      .replace(/&amp;/g, '&')
      .replace(/&lt;/g, '<')
      .replace(/&gt;/g, '>')
      .replace(/\s+/g, ' ')
      .trim();
  }
  
  /**
   * Преобразование в полный тип
   */
  private asCompany(data: Partial<JSpravCompany>): JSpravCompany {
    return {
      name: data.name || '',
      address: data.address || '',
      phone: data.phone || '',
      email: data.email || null,
      website: data.website || null,
      category: data.category || '',
      city: data.city || '',
      rating: data.rating || null,
      reviewsCount: data.reviewsCount || null,
      sourceUrl: data.sourceUrl || '',
      parsedAt: data.parsedAt || new Date().toISOString(),
    };
  }
  
  /**
   * Основной метод парсинга
   */
  async scrape(config: JSpravScraperConfig): Promise<JSpravCompany[]> {
    await this.init();
    this.results = [];
    
    const baseUrl = this.getCityUrl(config.city);
    console.log(`\n📍 Base URL: ${baseUrl}`);
    
    for (const category of config.categories) {
      console.log(`\n📂 Processing category: ${category}`);
      
      for (let page = 1; page <= config.maxPagesPerCategory; page++) {
        const pageUrl = page === 1 
          ? `${baseUrl}/${category}/`
          : `${baseUrl}/${category}/?page=${page}`;
        
        console.log(`  📄 Page ${page}: ${pageUrl}`);
        
        try {
          const html = await this.fetchPage(pageUrl);
          const companies = this.parseCategoryPage(html, config.city, category);
          
          if (companies.length === 0) {
            console.log(`  ⚠️ No companies found, stopping pagination`);
            break;
          }
          
          console.log(`  ✓ Found ${companies.length} companies`);
          
          // Обогащение данных (опционально)
          for (const company of companies) {
            const enriched = await this.enrichCompanyData(company);
            this.results.push(enriched);
          }
          
          // Задержка между запросами
          if (config.delayBetweenRequests > 0) {
            await new Promise(r => setTimeout(r, config.delayBetweenRequests));
          }
          
        } catch (error: any) {
          console.error(`  ❌ Error: ${error.message}`);
          break;
        }
      }
    }
    
    console.log(`\n✅ Total companies scraped: ${this.results.length}`);
    return this.results;
  }
  
  /**
   * Экспорт результатов в JSON
   */
  exportToJson(filename: string = 'jsprav_companies.json'): void {
    const fs = require('fs');
    fs.writeFileSync(filename, JSON.stringify(this.results, null, 2), 'utf-8');
    console.log(`📁 Exported to ${filename}`);
  }
}

// ============================================
// ИСПОЛЬЗОВАНИЕ
// ============================================

async function main() {
  const scraper = new JSpravScraper();
  
  const companies = await scraper.scrape({
    city: 'москва',
    categories: ['avtoservisy', 'restorany', 'apteki'],
    maxPagesPerCategory: 3,
    delayBetweenRequests: 1000,
  });
  
  scraper.exportToJson('moscow_companies.json');
  
  // Вывод первых 5 компаний
  console.log('\n📋 Sample results:');
  companies.slice(0, 5).forEach((c, i) => {
    console.log(`${i + 1}. ${c.name}`);
    console.log(`   📍 ${c.address}`);
    console.log(`   📞 ${c.phone}`);
    console.log(`   ⭐ ${c.rating || 'N/A'}`);
  });
}

main().catch(console.error);
```

### Упрощённая версия для быстрого старта

```typescript
import ZAI from 'z-ai-web-dev-sdk';

async function quickScrapeJSprav(city: string, category: string) {
  const zai = await ZAI.create();
  
  // Формирование URL
  const url = `https://${city}.jsprav.ru/${category}/`;
  
  console.log(`Reading: ${url}`);
  
  // Получение страницы
  const result = await zai.functions.invoke('page_reader', {
    url: url
  });
  
  const html = result.data.html;
  const title = result.data.title;
  
  console.log(`\n📌 Page: ${title}`);
  console.log(`📏 Content length: ${html.length} chars`);
  
  // Простой поиск компаний по паттернам
  const phonePattern = /\+7\s*[\(]?\d{3}[\)]?\s*\d{3}[-\s]?\d{2}[-\s]?\d{2}/g;
  const phones = html.match(phonePattern) || [];
  
  const emailPattern = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g;
  const emails = html.match(emailPattern) || [];
  
  console.log(`\n📞 Found ${phones.length} phone numbers`);
  console.log(`📧 Found ${emails.length} emails`);
  
  // Вывод уникальных значений
  console.log('\n📋 Unique phones:', [...new Set(phones)].slice(0, 5));
  console.log('📧 Unique emails:', [...new Set(emails)].slice(0, 5));
  
  return { html, phones, emails };
}

// Запуск
quickScrapeJSprav('moskva1', 'cat/avtoservisy');
```

---

## 6. Обработка ошибок

### Типичные ошибки и решения

```typescript
import ZAI from 'z-ai-web-dev-sdk';

enum PageReaderError {
  TIMEOUT = 'TIMEOUT',
  NOT_FOUND = 'NOT_FOUND',
  FORBIDDEN = 'FORBIDDEN',
  INVALID_URL = 'INVALID_URL',
  EMPTY_CONTENT = 'EMPTY_CONTENT',
  UNKNOWN = 'UNKNOWN',
}

interface PageReaderResult {
  success: boolean;
  error?: PageReaderError;
  errorMessage?: string;
  data?: any;
}

async function safeReadPage(url: string): Promise<PageReaderResult> {
  // Валидация URL
  try {
    new URL(url);
  } catch {
    return {
      success: false,
      error: PageReaderError.INVALID_URL,
      errorMessage: `Invalid URL format: ${url}`,
    };
  }
  
  try {
    const zai = await ZAI.create();
    const result = await zai.functions.invoke('page_reader', { url });
    
    // Анализ ответа
    if (result.code === 404 || result.warning?.includes('404')) {
      return {
        success: false,
        error: PageReaderError.NOT_FOUND,
        errorMessage: 'Page not found (404)',
      };
    }
    
    if (result.code === 403 || result.warning?.includes('403')) {
      return {
        success: false,
        error: PageReaderError.FORBIDDEN,
        errorMessage: 'Access forbidden (403)',
      };
    }
    
    if (!result.data?.html || result.data.html.length < 100) {
      return {
        success: false,
        error: PageReaderError.EMPTY_CONTENT,
        errorMessage: 'Page returned empty or very short content',
      };
    }
    
    return {
      success: true,
      data: result.data,
    };
    
  } catch (error: any) {
    const message = error.message || 'Unknown error';
    
    if (message.includes('timeout') || message.includes('deadline')) {
      return {
        success: false,
        error: PageReaderError.TIMEOUT,
        errorMessage: message,
      };
    }
    
    return {
      success: false,
      error: PageReaderError.UNKNOWN,
      errorMessage: message,
    };
  }
}

// Использование с обработкой всех случаев
async function demonstrate() {
  const urls = [
    'https://moskva1.jsprav.ru/cat/avtoservisy/',
    'https://invalid-url-12345.com',
    'https://moskva1.jsprav.ru/nonexistent/',
  ];
  
  for (const url of urls) {
    console.log(`\n🔍 Testing: ${url}`);
    
    const result = await safeReadPage(url);
    
    if (result.success) {
      console.log(`✅ Success: ${result.data.title}`);
      console.log(`   Content: ${result.data.html.length} chars`);
    } else {
      console.log(`❌ Error [${result.error}]: ${result.errorMessage}`);
    }
  }
}

demonstrate();
```

### Централизованная обработка ошибок

```typescript
import ZAI from 'z-ai-web-dev-sdk';

class ErrorHandler {
  private errorCounts: Map<string, number> = new Map();
  private maxErrorsPerType = 10;
  
  handleError(error: PageReaderError, url: string): boolean {
    const key = `${error}:${new URL(url).hostname}`;
    const count = (this.errorCounts.get(key) || 0) + 1;
    this.errorCounts.set(key, count);
    
    console.error(`[${error}] ${url} (count: ${count})`);
    
    // Если слишком много ошибок одного типа на одном домене
    if (count >= this.maxErrorsPerType) {
      console.error(`⚠️ Too many ${error} errors for this domain. Consider stopping.`);
      return false;
    }
    
    return true;
  }
  
  getErrorStats(): Record<string, number> {
    return Object.fromEntries(this.errorCounts);
  }
}
```

---

## 7. Оптимизация и кэширование

### Кэширование с TTL

```typescript
import ZAI from 'z-ai-web-dev-sdk';

interface CacheEntry<T> {
  data: T;
  timestamp: number;
  ttl: number;
}

class SmartCache<T> {
  private cache: Map<string, CacheEntry<T>> = new Map();
  private defaultTtl: number;
  
  constructor(defaultTtlMs: number = 3600000) {
    this.defaultTtl = defaultTtlMs;
  }
  
  get(key: string): T | null {
    const entry = this.cache.get(key);
    
    if (!entry) return null;
    
    if (Date.now() - entry.timestamp > entry.ttl) {
      this.cache.delete(key);
      return null;
    }
    
    return entry.data;
  }
  
  set(key: string, data: T, ttl?: number): void {
    this.cache.set(key, {
      data,
      timestamp: Date.now(),
      ttl: ttl || this.defaultTtl,
    });
  }
  
  has(key: string): boolean {
    return this.get(key) !== null;
  }
  
  clear(): void {
    this.cache.clear();
  }
  
  size(): number {
    return this.cache.size;
  }
}

// Использование с Page Reader
class CachedPageReader {
  private zai: Awaited<ReturnType<typeof ZAI.create>> | null = null;
  private cache: SmartCache<any>;
  
  constructor(cacheTtlMs: number = 1800000) {
    this.cache = new SmartCache(cacheTtlMs);
  }
  
  async init(): Promise<void> {
    this.zai = await ZAI.create();
  }
  
  async read(url: string, forceRefresh: boolean = false): Promise<any> {
    if (!forceRefresh && this.cache.has(url)) {
      console.log(`[Cache HIT] ${url}`);
      return this.cache.get(url);
    }
    
    console.log(`[Cache MISS] ${url}`);
    
    const result = await this.zai!.functions.invoke('page_reader', { url });
    this.cache.set(url, result.data);
    
    return result.data;
  }
}
```

### Rate Limiting

```typescript
class RateLimiter {
  private requests: number[] = [];
  private maxRequestsPerMinute: number;
  
  constructor(maxRequestsPerMinute: number = 30) {
    this.maxRequestsPerMinute = maxRequestsPerMinute;
  }
  
  async waitForSlot(): Promise<void> {
    const now = Date.now();
    const oneMinuteAgo = now - 60000;
    
    // Удаление старых запросов
    this.requests = this.requests.filter(t => t > oneMinuteAgo);
    
    // Проверка лимита
    if (this.requests.length >= this.maxRequestsPerMinute) {
      const oldestRequest = this.requests[0];
      const waitTime = 60000 - (now - oldestRequest) + 100;
      
      console.log(`⏳ Rate limit reached. Waiting ${Math.round(waitTime / 1000)}s...`);
      await new Promise(r => setTimeout(r, waitTime));
      
      return this.waitForSlot();
    }
    
    this.requests.push(now);
  }
  
  getStatus(): { current: number; limit: number; available: number } {
    const now = Date.now();
    const oneMinuteAgo = now - 60000;
    this.requests = this.requests.filter(t => t > oneMinuteAgo);
    
    return {
      current: this.requests.length,
      limit: this.maxRequestsPerMinute,
      available: this.maxRequestsPerMinute - this.requests.length,
    };
  }
}

// Использование
const rateLimiter = new RateLimiter(20); // 20 запросов в минуту

async function readWithRateLimit(url: string) {
  await rateLimiter.waitForSlot();
  // ... вызов page_reader
}
```

---

## 8. Примеры для типовых задач

### Задача 1: Извлечь контактную информацию

```typescript
import ZAI from 'z-ai-web-dev-sdk';

interface ContactInfo {
  phones: string[];
  emails: string[];
  websites: string[];
  addresses: string[];
}

async function extractContacts(url: string): Promise<ContactInfo> {
  const zai = await ZAI.create();
  const result = await zai.functions.invoke('page_reader', { url });
  
  const html = result.data.html;
  const text = result.data.text || html;
  
  // Паттерны для извлечения
  const phonePattern = /(?:\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}/g;
  const emailPattern = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g;
  const websitePattern = /https?:\/\/[^\s<>"']+\.[a-zA-Z]{2,}/g;
  const addressPattern = /(?:г\.|город|ул\.|улица|д\.|дом|кв\.|квартира)[\s\w\d\.,\-]+/gi;
  
  return {
    phones: [...new Set(html.match(phonePattern) || [])],
    emails: [...new Set(html.match(emailPattern) || [])],
    websites: [...new Set(text.match(websitePattern) || [])].filter(w => !w.includes('jsprav.ru')),
    addresses: [...new Set(text.match(addressPattern) || [])].slice(0, 5),
  };
}

// Использование
const contacts = await extractContacts('https://moskva1.jsprav.ru/company/12345/');
console.log('📞 Phones:', contacts.phones);
console.log('📧 Emails:', contacts.emails);
console.log('🌐 Websites:', contacts.websites);
```

### Задача 2: Пакетная обработка URL

```typescript
import ZAI from 'z-ai-web-dev-sdk';
import fs from 'fs';

interface BatchResult {
  url: string;
  success: boolean;
  title?: string;
  error?: string;
}

async function batchProcess(
  urls: string[], 
  concurrency: number = 3,
  outputPath?: string
): Promise<BatchResult[]> {
  const zai = await ZAI.create();
  const results: BatchResult[] = [];
  
  for (let i = 0; i < urls.length; i += concurrency) {
    const batch = urls.slice(i, i + concurrency);
    
    console.log(`\n📦 Processing batch ${Math.floor(i / concurrency) + 1}/${Math.ceil(urls.length / concurrency)}`);
    
    const batchResults = await Promise.allSettled(
      batch.map(async (url) => {
        const result = await zai.functions.invoke('page_reader', { url });
        return {
          url,
          success: result.code === 200,
          title: result.data?.title,
        };
      })
    );
    
    for (const r of batchResults) {
      if (r.status === 'fulfilled') {
        results.push(r.value);
        console.log(`  ✅ ${r.value.url}: ${r.value.title || 'No title'}`);
      } else {
        results.push({
          url: batch[batchResults.indexOf(r)],
          success: false,
          error: r.reason?.message || 'Unknown error',
        });
        console.log(`  ❌ Error: ${r.reason?.message}`);
      }
    }
    
    // Задержка между батчами
    if (i + concurrency < urls.length) {
      await new Promise(r => setTimeout(r, 1000));
    }
  }
  
  // Экспорт результатов
  if (outputPath) {
    fs.writeFileSync(outputPath, JSON.stringify(results, null, 2));
    console.log(`\n📁 Results saved to: ${outputPath}`);
  }
  
  // Статистика
  const successful = results.filter(r => r.success).length;
  console.log(`\n📊 Summary: ${successful}/${results.length} successful`);
  
  return results;
}

// Использование
const urls = [
  'https://moskva1.jsprav.ru/cat/avtoservisy/',
  'https://moskva1.jsprav.ru/cat/restorany/',
  'https://moskva1.jsprav.ru/cat/apteki/',
];

await batchProcess(urls, 2, 'batch_results.json');
```

### Задача 3: Мониторинг изменений страницы

```typescript
import ZAI from 'z-ai-web-dev-sdk';
import crypto from 'crypto';

interface PageSnapshot {
  url: string;
  hash: string;
  title: string;
  contentLength: number;
  timestamp: string;
}

class PageMonitor {
  private zai: Awaited<ReturnType<typeof ZAI.create>> | null = null;
  private snapshots: Map<string, PageSnapshot> = new Map();
  
  async init(): Promise<void> {
    this.zai = await ZAI.create();
  }
  
  private hashContent(content: string): string {
    return crypto.createHash('md5').update(content).digest('hex');
  }
  
  async check(url: string): Promise<{
    changed: boolean;
    previous?: PageSnapshot;
    current: PageSnapshot;
  }> {
    const result = await this.zai!.functions.invoke('page_reader', { url });
    
    const current: PageSnapshot = {
      url,
      hash: this.hashContent(result.data.html),
      title: result.data.title,
      contentLength: result.data.html.length,
      timestamp: new Date().toISOString(),
    };
    
    const previous = this.snapshots.get(url);
    const changed = previous ? previous.hash !== current.hash : false;
    
    if (changed || !previous) {
      this.snapshots.set(url, current);
    }
    
    return { changed, previous, current };
  }
}

// Использование
const monitor = new PageMonitor();
await monitor.init();

const result = await monitor.check('https://moskva1.jsprav.ru/cat/avtoservisy/');

if (result.changed) {
  console.log('🔄 Page changed!');
  console.log('Previous:', result.previous?.timestamp);
  console.log('Current:', result.current.timestamp);
} else {
  console.log('✅ No changes detected');
}
```

---

## 9. Чек-лист для ИИ-агента

### Перед началом работы

```
□ Проверить установку z-ai-web-dev-sdk
□ Импортировать SDK: import ZAI from 'z-ai-web-dev-sdk'
□ Создать экземпляр: const zai = await ZAI.create()
□ Проверить URL на валидность
```

### При парсинге страницы

```
□ Вызвать zai.functions.invoke('page_reader', { url })
□ Проверить result.code === 200
□ Проверить наличие result.data.html
□ Обработать ошибки через try-catch
□ Добавить задержку между запросами (1-2 сек)
```

### При обработке данных

```
□ Извлечь нужные данные из HTML
□ Очистить текст от HTML-тегов
□ Удалить дубликаты
□ Валидировать извлечённые данные
□ Сохранить результаты
```

### Код-шаблон для ИИ-агента

```typescript
import ZAI from 'z-ai-web-dev-sdk';

// ==========================================
// ШАБЛОН ДЛЯ ИИ-АГЕНТА
// ==========================================

async function agentParsePage(url: string) {
  // 1. Инициализация
  const zai = await ZAI.create();
  
  // 2. Запрос
  const result = await zai.functions.invoke('page_reader', { url });
  
  // 3. Проверка успеха
  if (result.code !== 200 || !result.data?.html) {
    throw new Error(`Failed: ${result.code}`);
  }
  
  // 4. Извлечение данных
  const { title, html, text } = result.data;
  
  // 5. Обработка данных
  // TODO: Ваш код здесь
  
  // 6. Возврат результата
  return { title, html, text };
}

// Запуск
agentParsePage('https://example.com')
  .then(console.log)
  .catch(console.error);
```

---

## Краткая шпаргалка

| Операция | Код |
|----------|-----|
| Инициализация | `const zai = await ZAI.create()` |
| Чтение страницы | `zai.functions.invoke('page_reader', { url })` |
| Получить HTML | `result.data.html` |
| Получить текст | `result.data.text` |
| Получить заголовок | `result.data.title` |
| Проверить успех | `result.code === 200` |

---

*Документ подготовлен для ИИ-агентов*
