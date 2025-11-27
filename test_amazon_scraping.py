"""Script de test pour déboguer le scraping Amazon.ca"""
import asyncio
import re
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

async def test_amazon_search():
    """Test le scraping d'une recherche Amazon.ca"""
    search_query = "nvidia"
    search_url = f"https://www.amazon.ca/s?k={search_query.replace(' ', '+')}"
    
    print(f"🔍 Test de scraping pour: {search_query}")
    print(f"🌐 URL: {search_url}\n")
    
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=True)
    context = await browser.new_context(
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        viewport={'width': 1920, 'height': 1080},
        locale='en-CA',
    )
    page = await context.new_page()
    
    try:
        print("⏳ Navigation vers Amazon.ca...")
        await page.goto(search_url, wait_until='domcontentloaded', timeout=60000)
        await asyncio.sleep(5)  # Attendre le chargement
        
        # Scroller pour charger plus de produits
        print("📜 Scroll pour charger les produits...")
        for i in range(3):
            await page.evaluate(f"window.scrollTo(0, {1000 * (i + 1)})")
            await asyncio.sleep(2)
        
        # Vérifier l'URL actuelle
        current_url = page.url
        print(f"📍 URL actuelle: {current_url}")
        
        # Obtenir le HTML
        html = await page.content()
        soup = BeautifulSoup(html, 'lxml')
        
        print(f"\n📊 Analyse du HTML:")
        print(f"   Taille HTML: {len(html)} caractères")
        print(f"   Contient 's-search-result': {'s-search-result' in html}")
        print(f"   Contient 'data-component-type': {'data-component-type' in html}")
        print(f"   Contient 'captcha': {'captcha' in html.lower()}")
        print(f"   Contient 'robot': {'robot' in html.lower()}")
        print(f"   Contient 'access denied': {'access denied' in html.lower()}")
        print(f"   Titre de la page: {soup.title.string if soup.title else 'Non trouvé'}\n")
        
        # Afficher un extrait du HTML
        print("📄 Extrait du HTML (premiers 1000 caractères):")
        print(html[:1000])
        print("\n")
        
        # Méthode 1: Chercher avec data-component-type
        product_containers_1 = soup.find_all('div', {'data-component-type': 's-search-result'})
        print(f"✅ Méthode 1 (data-component-type='s-search-result'): {len(product_containers_1)} produits trouvés")
        
        # Méthode 2: Chercher avec data-asin
        product_containers_2 = soup.find_all('div', {'data-asin': True})
        print(f"✅ Méthode 2 (data-asin présent): {len(product_containers_2)} produits trouvés")
        
        # Méthode 3: Chercher avec class contenant "s-result-item"
        product_containers_3 = soup.find_all('div', {'class': re.compile(r's-result-item', re.I)})
        print(f"✅ Méthode 3 (class='s-result-item'): {len(product_containers_3)} produits trouvés")
        
        # Méthode 4: Chercher tous les divs avec data-asin
        all_with_asin = soup.find_all(attrs={'data-asin': True})
        print(f"✅ Méthode 4 (tous éléments avec data-asin): {len(all_with_asin)} éléments trouvés")
        
        # Analyser le premier produit trouvé
        if product_containers_1:
            print(f"\n🔍 Analyse du premier produit (Méthode 1):")
            container = product_containers_1[0]
            asin = container.get('data-asin')
            print(f"   ASIN: {asin}")
            
            # Titre
            title_elem = container.find('h2', {'class': re.compile(r's-title', re.I)})
            if not title_elem:
                title_elem = container.find('span', {'class': re.compile(r'text-normal', re.I)})
            if not title_elem:
                title_elem = container.find('h2')
            title = title_elem.get_text(strip=True) if title_elem else "Non trouvé"
            print(f"   Titre: {title[:80]}...")
            
            # Prix
            price_elem = container.find('span', {'class': 'a-price-whole'})
            if price_elem:
                print(f"   Prix trouvé (a-price-whole): {price_elem.get_text(strip=True)}")
            else:
                price_elem = container.find('span', {'class': 'a-offscreen'})
                if price_elem:
                    print(f"   Prix trouvé (a-offscreen): {price_elem.get_text(strip=True)}")
                else:
                    print(f"   ❌ Prix non trouvé")
            
            # Note
            rating_elem = container.find('span', {'class': re.compile(r'a-icon-alt', re.I)})
            if rating_elem:
                print(f"   Note trouvée: {rating_elem.get_text(strip=True)}")
            else:
                print(f"   ❌ Note non trouvée")
        
        # Analyser avec la méthode 2
        if product_containers_2 and not product_containers_1:
            print(f"\n🔍 Analyse du premier produit (Méthode 2):")
            container = product_containers_2[0]
            asin = container.get('data-asin')
            print(f"   ASIN: {asin}")
            
            # Chercher le titre dans le parent ou les enfants
            title_elem = container.find('h2')
            if not title_elem:
                title_elem = container.find('span', {'class': re.compile(r'text', re.I)})
            title = title_elem.get_text(strip=True) if title_elem else "Non trouvé"
            print(f"   Titre: {title[:80]}...")
        
        # Sauvegarder un extrait du HTML pour analyse
        if product_containers_1:
            sample_html = str(product_containers_1[0])[:500]
            print(f"\n📄 Extrait HTML du premier produit:")
            print(sample_html)
        elif product_containers_2:
            sample_html = str(product_containers_2[0])[:500]
            print(f"\n📄 Extrait HTML du premier produit (méthode 2):")
            print(sample_html)
        else:
            # Chercher n'importe quel div avec data-asin
            any_asin = soup.find(attrs={'data-asin': True})
            if any_asin:
                print(f"\n📄 Extrait HTML d'un élément avec ASIN:")
                print(str(any_asin)[:500])
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await browser.close()
        await playwright.stop()

if __name__ == "__main__":
    asyncio.run(test_amazon_search())

