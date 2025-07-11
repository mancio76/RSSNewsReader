#!/usr/bin/env python3
"""
CLI Manager per RSSNewsReader
Gestione dati attraverso interfaccia a riga di comando
"""

import sys
import os
from datetime import datetime
from typing import Optional, List

# Aggiungi il percorso root del progetto al PYTHONPATH
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from app.models import Source, Article, Tag, ArticleTag
from app.models.base import SessionLocal, create_tables
from sqlalchemy import func

class CLIManager:
    """Manager per interfaccia a riga di comando"""
    
    def __init__(self):
        self.db = SessionLocal()
        
        # Assicurati che le tabelle esistano
        create_tables()
        
        print("🗞️  RSSNewsReader CLI Manager")
        print("=" * 50)
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.db.close()
    
    def show_menu(self):
        """Mostra il menu principale"""
        print("\n📋 Menu Principale:")
        print("1. Elenca article")
        print("2. Elimina article")
        print("3. Elimina tutti gli article")
        print("4. Elenca source")
        print("5. Elimina source")
        print("6. Modifica source")
        print("7. Aggiungi source")
        print("8. Elimina tutte le source")
        print("0. Quit")
        print("-" * 30)
    
    def get_user_choice(self) -> str:
        """Ottieni la scelta dell'utente"""
        try:
            choice = input("Inserisci la tua scelta (0-8): ").strip()
            return choice
        except KeyboardInterrupt:
            print("\n\n👋 Arrivederci!")
            sys.exit(0)
        except EOFError:
            return "0"
    
    def format_datetime(self, dt: Optional[datetime]) -> str:
        """Formatta datetime per visualizzazione"""
        if dt:
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        return "N/A"
    
    def truncate_text(self, text: str, max_length: int = 80) -> str:
        """Tronca testo per visualizzazione"""
        if not text:
            return "N/A"
        if len(text) <= max_length:
            return text
        return text[:max_length-3] + "..."
    
    def list_articles(self):
        """Lista tutti gli articoli"""
        try:
            print("\n📄 Lista Articoli:")
            print("=" * 120)
            
            # Query con join per ottenere nome source
            articles = self.db.query(Article).join(Source).order_by(Article.scraped_date.desc()).all()
            
            if not articles:
                print("ℹ️  Nessun articolo trovato nel database.")
                return
            
            # Header tabella
            print(f"{'ID':<5} {'Title':<50} {'Source':<20} {'Date':<20} {'URL':<25}")
            print("-" * 120)
            
            for article in articles:
                print(f"{article.id:<5} "
                      f"{self.truncate_text(article.title, 48):<50} "
                      f"{self.truncate_text(article.source.name, 18):<20} "
                      f"{self.format_datetime(article.published_date):<20} "
                      f"{self.truncate_text(article.url, 23):<25}")
            
            print(f"\n📊 Totale: {len(articles)} articoli")
            
            # Statistiche aggiuntive
            total_words = sum(article.word_count or 0 for article in articles)
            avg_words = total_words / len(articles) if articles else 0
            
            print(f"📈 Statistiche: {total_words:,} parole totali, {avg_words:.1f} parole in media")
            
        except Exception as e:
            print(f"❌ Errore nel listare gli articoli: {str(e)}")
    
    def delete_article(self):
        """Elimina un singolo articolo"""
        try:
            article_id = input("Inserisci l'ID dell'articolo da eliminare: ").strip()
            
            if not article_id.isdigit():
                print("❌ ID articolo deve essere un numero.")
                return
            
            article_id = int(article_id)
            
            # Trova l'articolo
            article = self.db.query(Article).filter_by(id=article_id).first()
            
            if not article:
                print(f"❌ Articolo con ID {article_id} non trovato.")
                return
            
            # Mostra dettagli articolo
            print(f"\n📄 Articolo da eliminare:")
            print(f"   ID: {article.id}")
            print(f"   Title: {article.title}")
            print(f"   Source: {article.source.name}")
            print(f"   URL: {article.url}")
            print(f"   Date: {self.format_datetime(article.published_date)}")
            
            # Conferma eliminazione
            confirm = input(f"\n⚠️  Sei sicuro di voler eliminare questo articolo? (y/N): ").strip().lower()
            
            if confirm in ['y', 'yes', 'si', 's']:
                self.db.delete(article)
                self.db.commit()
                print(f"✅ Articolo {article_id} eliminato con successo.")
            else:
                print("❌ Eliminazione annullata.")
                
        except ValueError:
            print("❌ ID articolo deve essere un numero valido.")
        except Exception as e:
            print(f"❌ Errore nell'eliminare l'articolo: {str(e)}")
            self.db.rollback()
    
    def delete_all_articles(self):
        """Elimina tutti gli articoli"""
        try:
            # Conta articoli
            total_articles = self.db.query(Article).count()
            
            if total_articles == 0:
                print("ℹ️  Nessun articolo da eliminare.")
                return
            
            print(f"\n⚠️  Stai per eliminare {total_articles} articoli.")
            confirm = input("Sei sicuro di voler eliminare TUTTI gli articoli? (y/N): ").strip().lower()
            
            if confirm in ['y', 'yes', 'si', 's']:
                # Elimina prima le associazioni
                self.db.query(ArticleTag).delete()
                
                # Poi elimina gli articoli
                deleted_count = self.db.query(Article).delete()
                self.db.commit()
                
                print(f"✅ Eliminati {deleted_count} articoli con successo.")
            else:
                print("❌ Eliminazione annullata.")
                
        except Exception as e:
            print(f"❌ Errore nell'eliminare tutti gli articoli: {str(e)}")
            self.db.rollback()
    
    def list_sources(self):
        """Lista tutte le sources"""
        try:
            print("\n📰 Lista Sources:")
            print("=" * 100)
            
            sources = self.db.query(Source).order_by(Source.name).all()
            
            if not sources:
                print("ℹ️  Nessuna source trovata nel database.")
                return
            
            # Header tabella
            print(f"{'ID':<5} {'Name':<25} {'Type':<8} {'Status':<8} {'Articles':<10} {'Last Scraped':<20}")
            print("-" * 100)
            
            for source in sources:
                # Conta articoli per source
                article_count = self.db.query(Article).filter_by(source_id=source.id).count()
                
                # Determina tipo source
                source_type = "RSS" if source.rss_url else "WEB"
                
                # Status
                status = "✅ Active" if source.is_active else "❌ Inactive"
                if source.error_count > 0:
                    status = f"⚠️  Errors({source.error_count})"
                
                print(f"{source.id:<5} "
                      f"{self.truncate_text(source.name, 23):<25} "
                      f"{source_type:<8} "
                      f"{status:<8} "
                      f"{article_count:<10} "
                      f"{self.format_datetime(source.last_scraped):<20}")
            
            print(f"\n📊 Totale: {len(sources)} sources")
            
            # Statistiche aggiuntive
            active_sources = len([s for s in sources if s.is_active])
            error_sources = len([s for s in sources if s.error_count > 0])
            rss_sources = len([s for s in sources if s.rss_url])
            web_sources = len(sources) - rss_sources
            
            print(f"📈 Statistiche: {active_sources} attive, {error_sources} con errori, {rss_sources} RSS, {web_sources} WEB")
            
        except Exception as e:
            print(f"❌ Errore nel listare le sources: {str(e)}")
    
    def delete_source(self):
        """Elimina una singola source"""
        try:
            source_id = input("Inserisci l'ID della source da eliminare: ").strip()
            
            if not source_id.isdigit():
                print("❌ ID source deve essere un numero.")
                return
            
            source_id = int(source_id)
            
            # Trova la source
            source = self.db.query(Source).filter_by(id=source_id).first()
            
            if not source:
                print(f"❌ Source con ID {source_id} non trovata.")
                return
            
            # Conta articoli correlati
            article_count = self.db.query(Article).filter_by(source_id=source_id).count()
            
            # Mostra dettagli source
            print(f"\n📰 Source da eliminare:")
            print(f"   ID: {source.id}")
            print(f"   Name: {source.name}")
            print(f"   URL: {source.base_url}")
            print(f"   RSS: {source.rss_url or 'N/A'}")
            print(f"   Articles: {article_count}")
            print(f"   Status: {'Active' if source.is_active else 'Inactive'}")
            
            # Conferma eliminazione
            if article_count > 0:
                print(f"\n⚠️  ATTENZIONE: Questa source ha {article_count} articoli associati che verranno eliminati!")
            
            confirm = input(f"\nSei sicuro di voler eliminare questa source? (y/N): ").strip().lower()
            
            if confirm in ['y', 'yes', 'si', 's']:
                self.db.delete(source)
                self.db.commit()
                print(f"✅ Source {source_id} eliminata con successo.")
            else:
                print("❌ Eliminazione annullata.")
                
        except ValueError:
            print("❌ ID source deve essere un numero valido.")
        except Exception as e:
            print(f"❌ Errore nell'eliminare la source: {str(e)}")
            self.db.rollback()

    def delete_all_sources(self):
        """Elimina tutti le source"""
        try:
            # Conta articoli
            total_sources = self.db.query(Source).count()
            
            if total_sources == 0:
                print("ℹ️  Nessuna source da eliminare.")
                return
            
            print(f"\n⚠️  Stai per eliminare {total_sources} source.")
            confirm = input("Sei sicuro di voler eliminare TUTTE le source? (y/N): ").strip().lower()
            
            if confirm in ['y', 'yes', 'si', 's']:

                # Conta articoli correlati
                article_count = self.db.query(Article).count()
                
                # Conferma eliminazione
                if article_count > 0:
                    print(f"\n⚠️  ATTENZIONE: Ci sono {article_count} articoli associati che verranno eliminati!")
                
                confirm = input(f"\nSei sicuro di voler eliminare TUTTE le source? (y/N): ").strip().lower()

                if confirm in ['y', 'yes', 'si', 's']:
                    deleted_count = self.db.query(Source).delete()
                    self.db.commit()
                    print(f"✅ Eliminate {deleted_count} source con successo.")
                else:
                    print("❌ Eliminazione annullata.")

            else:
                print("❌ Eliminazione annullata.")
                
        except Exception as e:
            print(f"❌ Errore nell'eliminare tutte le source: {str(e)}")
            self.db.rollback()

    def modify_source(self):
        """Modifica una source esistente"""
        try:
            source_id = input("Inserisci l'ID della source da modificare: ").strip()
            
            if not source_id.isdigit():
                print("❌ ID source deve essere un numero.")
                return
            
            source_id = int(source_id)
            
            # Trova la source
            source = self.db.query(Source).filter_by(id=source_id).first()
            
            if not source:
                print(f"❌ Source con ID {source_id} non trovata.")
                return
            
            # Mostra dettagli attuali
            print(f"\n📰 Source da modificare:")
            print(f"   ID: {source.id}")
            print(f"   Name: {source.name}")
            print(f"   Base URL: {source.base_url}")
            print(f"   RSS URL: {source.rss_url or 'N/A'}")
            print(f"   Description: {source.description or 'N/A'}")
            print(f"   Active: {'Yes' if source.is_active else 'No'}")
            print(f"   Rate Limit: {source.rate_limit_delay} seconds")
            print(f"   Update Frequency: {source.update_frequency} seconds")
            
            print(f"\n🔧 Modifica campi (premi Enter per mantenere il valore attuale):")
            
            # Nome
            new_name = input(f"Name [{source.name}]: ").strip()
            if new_name:
                source.name = new_name
            
            # Base URL
            new_base_url = input(f"Base URL [{source.base_url}]: ").strip()
            if new_base_url:
                source.base_url = new_base_url
            
            # RSS URL
            current_rss = source.rss_url or ""
            new_rss_url = input(f"RSS URL [{current_rss}]: ").strip()
            if new_rss_url != current_rss:
                source.rss_url = new_rss_url if new_rss_url else None
            
            # Description
            current_desc = source.description or ""
            new_description = input(f"Description [{current_desc}]: ").strip()
            if new_description != current_desc:
                source.description = new_description if new_description else None
            
            # Active status
            current_active = "y" if source.is_active else "n"
            new_active = input(f"Active (y/n) [{current_active}]: ").strip().lower()
            if new_active and new_active in ['y', 'n', 'yes', 'no']:
                source.is_active = new_active in ['y', 'yes']
            
            # Rate limit
            new_rate_limit = input(f"Rate Limit Delay (seconds) [{source.rate_limit_delay}]: ").strip()
            if new_rate_limit and new_rate_limit.isdigit():
                source.rate_limit_delay = int(new_rate_limit)
            
            # Update frequency
            new_frequency = input(f"Update Frequency (seconds) [{source.update_frequency}]: ").strip()
            if new_frequency and new_frequency.isdigit():
                source.update_frequency = int(new_frequency)
            
            # Scraping config (avanzato)
            modify_config = input("Vuoi modificare la configurazione di scraping? (y/n): ").strip().lower()
            if modify_config in ['y', 'yes', 'si', 's']:
                self._modify_scraping_config(source)
            
            # Conferma modifiche
            print(f"\n📋 Riepilogo modifiche:")
            print(f"   Name: {source.name}")
            print(f"   Base URL: {source.base_url}")
            print(f"   RSS URL: {source.rss_url or 'N/A'}")
            print(f"   Description: {source.description or 'N/A'}")
            print(f"   Active: {'Yes' if source.is_active else 'No'}")
            print(f"   Rate Limit: {source.rate_limit_delay} seconds")
            print(f"   Update Frequency: {source.update_frequency} seconds")
            
            confirm = input(f"\nConfermi le modifiche? (y/N): ").strip().lower()
            
            if confirm in ['y', 'yes', 'si', 's']:
                source.updated_date = datetime.now(datetime.timezone.utc)
                self.db.commit()
                print(f"✅ Source {source_id} modificata con successo.")
            else:
                self.db.rollback()
                print("❌ Modifiche annullate.")
                
        except ValueError:
            print("❌ Valori numerici non validi.")
        except Exception as e:
            print(f"❌ Errore nella modifica della source: {str(e)}")
            self.db.rollback()
    
    def _modify_scraping_config(self, source: Source):
        """Modifica configurazione di scraping"""
        try:
            config = source.scraping_config or {}
            
            print(f"\n🔧 Configurazione scraping attuale:")
            for key, value in config.items():
                print(f"   {key}: {value}")
            
            print(f"\nCampi configurabili:")
            print("   - article_list_selector: Selettore per lista articoli")
            print("   - title_selector: Selettore per titolo")
            print("   - content_selector: Selettore per contenuto")
            print("   - url_selector: Selettore per URL")
            print("   - date_selector: Selettore per data")
            print("   - author_selector: Selettore per autore")
            
            modify_config = input("Vuoi modificare la configurazione? (y/n): ").strip().lower()
            if modify_config not in ['y', 'yes', 'si', 's']:
                return
            
            # Modifica selettori
            selectors = [
                ('article_list_selector', 'Lista articoli'),
                ('title_selector', 'Titolo'),
                ('content_selector', 'Contenuto'),
                ('url_selector', 'URL'),
                ('date_selector', 'Data'),
                ('author_selector', 'Autore')
            ]
            
            for selector_key, selector_name in selectors:
                current_value = config.get(selector_key, '')
                new_value = input(f"{selector_name} [{current_value}]: ").strip()
                if new_value:
                    config[selector_key] = new_value
                elif new_value == '' and selector_key in config:
                    del config[selector_key]
            
            source.scraping_config = config if config else None
            
        except Exception as e:
            print(f"❌ Errore nella modifica della configurazione: {str(e)}")
    
    def add_source(self):
        """Aggiungi una nuova source"""
        try:
            print(f"\n➕ Aggiungi nuova source:")
            print("=" * 40)
            
            # Campi obbligatori
            name = input("Nome source (obbligatorio): ").strip()
            if not name:
                print("❌ Nome source è obbligatorio.")
                return
            
            base_url = input("Base URL (obbligatorio): ").strip()
            if not base_url:
                print("❌ Base URL è obbligatorio.")
                return
            
            # Controlla duplicati
            existing = self.db.query(Source).filter_by(name=name).first()
            if existing:
                print(f"❌ Source con nome '{name}' esiste già.")
                return
            
            # Campi opzionali
            rss_url = input("RSS URL (opzionale): ").strip()
            description = input("Descrizione (opzionale): ").strip()
            
            # Configurazione
            print(f"\n🔧 Configurazione:")
            active = input("Attiva source? (Y/n): ").strip().lower()
            is_active = active not in ['n', 'no']
            
            rate_limit = input("Rate limit delay in secondi (default: 2): ").strip()
            rate_limit_delay = int(rate_limit) if rate_limit.isdigit() else 2
            
            frequency = input("Update frequency in secondi (default: 3600): ").strip()
            update_frequency = int(frequency) if frequency.isdigit() else 3600
            
            # Configurazione scraping
            scraping_config = None
            if not rss_url:
                print(f"\n🕷️  Configurazione Web Scraping:")
                print("Per siti senza RSS, devi configurare i selettori CSS.")
                
                setup_scraping = input("Vuoi configurare il web scraping? (y/N): ").strip().lower()
                if setup_scraping in ['y', 'yes', 'si', 's']:
                    scraping_config = self._setup_scraping_config()
            
            # Crea source
            source = Source(
                name=name,
                base_url=base_url,
                rss_url=rss_url if rss_url else None,
                description=description if description else None,
                is_active=is_active,
                rate_limit_delay=rate_limit_delay,
                update_frequency=update_frequency,
                scraping_config=scraping_config,
                created_date=datetime.now(datetime.timezone.utc),
                updated_date=datetime.now(datetime.timezone.utc)
            )
            
            # Mostra riepilogo
            print(f"\n📋 Riepilogo nuova source:")
            print(f"   Name: {source.name}")
            print(f"   Base URL: {source.base_url}")
            print(f"   RSS URL: {source.rss_url or 'N/A'}")
            print(f"   Description: {source.description or 'N/A'}")
            print(f"   Active: {'Yes' if source.is_active else 'No'}")
            print(f"   Rate Limit: {source.rate_limit_delay} seconds")
            print(f"   Update Frequency: {source.update_frequency} seconds")
            print(f"   Scraping Config: {'Yes' if source.scraping_config else 'No'}")
            
            confirm = input(f"\nConfermi la creazione? (y/N): ").strip().lower()
            
            if confirm in ['y', 'yes', 'si', 's']:
                self.db.add(source)
                self.db.commit()
                print(f"✅ Source '{name}' creata con successo (ID: {source.id}).")
            else:
                print("❌ Creazione annullata.")
                
        except ValueError:
            print("❌ Valori numerici non validi.")
        except Exception as e:
            print(f"❌ Errore nella creazione della source: {str(e)}")
            self.db.rollback()
    
    def _setup_scraping_config(self) -> dict:
        """Setup configurazione scraping"""
        config = {}
        
        print(f"\n🔧 Configurazione selettori CSS:")
        print("Lascia vuoto per usare i default.")
        
        selectors = [
            ('article_list_selector', 'Lista articoli', 'article'),
            ('title_selector', 'Titolo', 'h1, h2, h3'),
            ('content_selector', 'Contenuto', 'p'),
            ('url_selector', 'URL', 'a'),
            ('date_selector', 'Data', 'time'),
            ('author_selector', 'Autore', '.author')
        ]
        
        for selector_key, selector_name, default_value in selectors:
            value = input(f"{selector_name} [{default_value}]: ").strip()
            config[selector_key] = value if value else default_value
        
        # Configurazione avanzata
        print(f"\n🔧 Configurazione avanzata:")
        
        follow_pagination = input("Segui paginazione? (y/N): ").strip().lower()
        if follow_pagination in ['y', 'yes', 'si', 's']:
            config['follow_pagination'] = True
            
            pagination_selector = input("Selettore paginazione [.pagination a]: ").strip()
            config['pagination_selector'] = pagination_selector if pagination_selector else '.pagination a'
            
            max_pages = input("Numero massimo pagine [3]: ").strip()
            config['max_pages'] = int(max_pages) if max_pages.isdigit() else 3
        
        max_articles = input("Numero massimo articoli [20]: ").strip()
        config['max_articles'] = int(max_articles) if max_articles.isdigit() else 20
        
        return config
        """Elimina tutte le sources"""
        try:
            # Conta sources e articoli
            total_sources = self.db.query(Source).count()
            total_articles = self.db.query(Article).count()
            
            if total_sources == 0:
                print("ℹ️  Nessuna source da eliminare.")
                return
            
            print(f"\n⚠️  Stai per eliminare {total_sources} sources e {total_articles} articoli associati.")
            confirm = input("Sei sicuro di voler eliminare TUTTE le sources? (y/N): ").strip().lower()
            
            if confirm in ['y', 'yes', 'si', 's']:
                # Elimina prima le associazioni
                self.db.query(ArticleTag).delete()
                
                # Poi elimina articoli
                self.db.query(Article).delete()
                
                # Infine elimina sources
                deleted_sources = self.db.query(Source).delete()
                self.db.commit()
                
                print(f"✅ Eliminate {deleted_sources} sources e {total_articles} articoli con successo.")
            else:
                print("❌ Eliminazione annullata.")
                
        except Exception as e:
            print(f"❌ Errore nell'eliminare tutte le sources: {str(e)}")
            self.db.rollback()
    
    def run(self):
        """Esegui il ciclo principale del CLI"""
        try:
            while True:
                self.show_menu()
                choice = self.get_user_choice()
                
                if choice == "0":
                    print("\n👋 Arrivederci!")
                    break
                elif choice == "1":
                    self.list_articles()
                elif choice == "2":
                    self.delete_article()
                elif choice == "3":
                    self.delete_all_articles()
                elif choice == "4":
                    self.list_sources()
                elif choice == "5":
                    self.delete_source()
                elif choice == "6":
                    self.modify_source()
                elif choice == "7":
                    self.add_source()
                elif choice == "8":
                    self.delete_all_sources()
                else:
                    print("❌ Scelta non valida. Riprova.")
                
                # Pausa prima di mostrare di nuovo il menu
                if choice != "0":
                    input("\n⏸️  Premi Enter per continuare...")
                    
        except KeyboardInterrupt:
            print("\n\n👋 Arrivederci!")
        except Exception as e:
            print(f"❌ Errore inaspettato: {str(e)}")

def main():
    """Funzione main"""
    try:
        with CLIManager() as cli:
            cli.run()
    except Exception as e:
        print(f"❌ Errore fatale: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()