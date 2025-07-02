#// app.py

from flask import Flask, render_template, request, redirect, url_for, flash, session, g, jsonify
import yfinance as yf
import plotly.graph_objects as go
import os, math
import json
import requests
import sqlite3
from functools import wraps
from datetime import datetime, timedelta

# Lokale Imports
from backend.accounts_to_database import ENDPOINT as AccountEndpoint, ENDPOINT
from backend.accounts_to_database import UTILITIES
from backend.trading import TradingEndpoint # Geänderter Import
from backend.leaderboard import LeaderboardEndpoint
from backend.depot_system import DepotEndpoint
from backend.tokens import TokenEndpoint
from backend.accounts_to_database import Settings

app = Flask(__name__)
ALPHA_VANTAGE_API_KEY = None
DATABASE_FILE = "backend/StockBroker.db"

def __init__():
    global ALPHA_VANTAGE_API_KEY, app
    try:
        with open('keys.json', 'r') as f:
            keys = json.load(f)
            secret_key = keys.get('APP_SECRET')
            app.secret_key = secret_key
            ALPHA_VANTAGE_API_KEY = keys.get('alpha_vantage_api_key')
    except FileNotFoundError:
        print("WARNUNG: keys.json nicht gefunden.")
        raise
    except json.JSONDecodeError:
        print("WARNUNG: keys.json ist kein valides JSON.")
        raise

    if not secret_key:
        print("WARNUNG: App_Secret nicht in keys.json gefunden oder Datei fehlerhaft.")
        raise

    if not ALPHA_VANTAGE_API_KEY:
        print("WARNUNG: Alpha Vantage API Key nicht in keys.json gefunden oder Datei fehlerhaft.")
        raise

__init__()

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE_FILE)
    return db
# if name is main gezwungene alternative
with app.app_context():
    local_conn = get_db()
    local_conn.commit()
    local_conn.close()

@app.teardown_appcontext
def close_connection(exception):
    """Schließt die Datenbankverbindung am Ende des Requests."""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@app.before_request
def load_user_settings():
    """Lädt die Benutzereinstellungen vor jeder Anfrage, wenn der Benutzer eingeloggt ist."""
    g.user_settings = None
    if 'user_id' in session:
        conn = get_db()
        g.user_settings = Settings.get_settings(conn, session['user_id'])

# --- eigener Decorator ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Bitte melde dich an, um diese Seite zu sehen.', 'warning')
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/cancel_order/<int:order_id>', methods=['POST'])
@login_required
def cancel_order_route(order_id):
    """Storniert einen Auftrag."""
    db = get_db()
    result = TradingEndpoint.cancel_order(db, session['user_id'], order_id)
    if result.get('success'):
        db.commit()
        flash(result.get('message'), 'success')
    else:
        flash(result.get('message'), 'error')
    return redirect(url_for('my_orders_page'))


# -- Konstanten für Dropdown-Optionen beim Graph --
AVAILABLE_PERIODS = [
    ("5d", "5 Tage"), ("1mo", "1 Monat"), ("2mo", "2 Monate"),
    ("6mo", "6 Monate"), ("1y", "1 Jahr"), ("2y", "2 Jahre"),
    ("5y", "5 Jahre"), ("ytd", "Seit Jahresbeginn"), ("max", "Maximal")
]
AVAILABLE_QUALITIES = [
    ("high", "Hoch"), ("normal", "Normal"), ("low", "Niedrig")
]

def do_login(conn, identifier:str=None , password:str=None, instant_login_result:dict=None) -> bool:
    result = AccountEndpoint.login(conn, identifier, password) if not instant_login_result else instant_login_result
    if result.get('success'):
        session['user_id'] = result.get('user_id')
        session['user_email'] = result.get('email')
        if result.get('username') is None:
            session['username'] = UTILITIES.get_username(conn, result.get('user_id'))
        else:
            session['username'] = result.get('username')
        flash(result.get('message', 'Login erfolgreich!'), 'success')
        conn.commit()
        return True
    else:
        flash(result.get('message', 'Login fehlgeschlagen.'), 'error')
        return False

#--AUTH--
@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if 'user_id' in session:
        return redirect(url_for('dashboard_page'))

    form_data = {}
    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip()
        password = request.form.get('password', '').strip()
        form_data['identifier'] = identifier

        if not identifier or not password:
            flash('Bitte Anmeldedaten eingeben.', 'error')
        else:
            conn = get_db()
            if do_login(conn, identifier, password):
                return redirect(url_for('dashboard_page'))

    return render_template('auth/login.html', form_data=form_data)

@app.route('/register', methods=['GET', 'POST'])
def register_page():
    if 'user_id' in session:
        return redirect(url_for('dashboard_page'))

    form_data = {}
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        password_confirm = request.form.get('password_confirm', '').strip()
        instant_token = request.form.get('instant_register_token', '').strip()

        form_data['email'] = email
        form_data['username'] = username

        if not email or not username or not password or not password_confirm:
            flash('Bitte alle Felder ausfüllen.', 'error')
        elif password != password_confirm:
            flash('Die Passwörter stimmen nicht überein.', 'error')
        else:
            conn = get_db()
            result = AccountEndpoint.create_account(conn, password, email, username,
                                                    instant_register_token=instant_token)

            if result.get('success'):
                conn.commit()
                if result.get('email_verification_required'):
                    # Leite auf eine Seite weiter, die den User anweist, seine E-Mails zu prüfen
                    flash(result.get('message'), 'info')
                    return redirect(url_for('verify_email_notice_page'))
                else:
                    # Account sofort aktiv
                    flash(result.get('message'), 'success')
                    return redirect(url_for('login_page'))
            else:
                flash(result.get('message', 'error'), 'error')

    return render_template('auth/register.html', form_data=form_data)

@app.route('/verify-notice')
def verify_email_notice_page():
    """Zeigt eine statische Seite, die den Nutzer anweist, seine E-Mail zu prüfen."""
    return render_template('auth/verify_email_notice.html')

@app.route('/verify-email', methods=['GET', 'POST'])
def verify_email_page():
    """Seite, auf der der Nutzer einen Token manuell eingeben kann."""
    if request.method == 'POST':
        token = request.form.get('token', '').strip()
        if not token:
            flash('Bitte gib den Code aus der E-Mail ein.', 'error')
        else:
            if do_email_token_verification(token):
                return redirect(url_for('dashboard_page'))
    return render_template('auth/verify_email.html')

@app.route('/verify/<token>')
def verify_email_from_link(token) -> redirect:
    """Verarbeitet den Token direkt aus dem E-Mail-Link."""
    if do_email_token_verification(token):
        return redirect(url_for('dashboard_page'))
    else:
        return redirect(url_for('register_page'))

def do_email_token_verification(token) -> bool:
    conn = get_db()
    result = AccountEndpoint.verify_email_delete_token(conn, token)
    conn.commit()
    if result.get('success'):
        user_id = result.get('user_id')
        if do_login(conn, UTILITIES.get_username(conn, user_id), instant_login_result=result):
            return True
    else:
        flash(result.get('message'), 'error')
    return False

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('user_email', None)
    session.pop('username', None)
    flash('Du wurdest erfolgreich ausgeloggt.', 'info')
    return redirect(url_for('login_page'))

@app.route('/reset-password-request', methods=['GET', 'POST'])
def reset_password_request_page():
    form_data = {}
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        form_data['email'] = email
        if not email:
            flash('Bitte gib deine E-Mail-Adresse ein.', 'error')
        else:
            conn = get_db()
            # Diese Funktion sendet jetzt die E-Mail
            AccountEndpoint.request_password_reset(conn, email)
            conn.commit()  # Wichtig, damit der Token gespeichert wird
            flash('Wenn ein Konto mit dieser E-Mail existiert, wurde eine Anleitung gesendet.', 'info')
            # Man leitet den User direkt zur Token-Eingabe
            return redirect(url_for('reset_password_enter_token_page'))

    return render_template('auth/reset_request.html', form_data=form_data)

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password_confirm_page(token):
    conn = get_db()
    # verify_reset_token gibt jetzt ein Dictionary zurück
    token_verification = TokenEndpoint.verify_but_not_consume_password_token(conn, token)
    if not token_verification.get('success'):
        # Token ist bereits konsumiert oder ungültig, commit ist nicht nötig
        flash(token_verification.get('message', 'Ungültiger oder abgelaufenes Token.'), 'error')
        return redirect(url_for('login_page'))

    if request.method == 'POST':
        new_password = request.form.get('new_password')
        new_password_confirm = request.form.get('new_password_confirm')

        if not new_password or not new_password_confirm:
            flash('Bitte gib das neue Passwort zweimal ein.', 'error')
        elif new_password != new_password_confirm:
            flash('Die neuen Passwörter stimmen nicht überein.', 'error')
        elif len(new_password) < 6:
            flash('Das neue Passwort muss mindestens 6 Zeichen lang sein.', 'error')
        else:
            #conn wird oben schon gemacht
            result = AccountEndpoint.reset_password_with_token(conn, token, new_password)
            conn.commit()
            if result.get('success'):
                username = UTILITIES.get_username(conn, result["user_id"])
                if do_login(conn, identifier=username, password=new_password):
                    flash(result.get('message', 'Passwort erfolgreich geändert.'), 'success')
                    return redirect(url_for('dashboard_page'))
                return redirect(url_for('login_page'))
            else:
                flash(result.get('message', 'Fehler beim Ändern des Passworts.'), 'error')
    return render_template('auth/reset_confirm.html', token=token)

@app.route('/reset-password-enter-token', methods=['GET', 'POST'])
def reset_password_enter_token_page():
    if request.method == 'POST':
        token = request.form.get('token', '').strip()
        if not token:
            flash('Bitte gib deinen Reset-Code ein.', 'error')
        else:
            return redirect(url_for('reset_password_confirm_page', token=token))
    return render_template('auth/reset_enter_token.html')
#//--AUTH--


def get_stock_basic_info_yfinance(ticker_symbol): # Renamed to avoid conflict
    try:
        stock = yf.Ticker(ticker_symbol)
        info = stock.info
        if not info or (info.get('longName') is None and info.get('shortName') is None and info.get('symbol') is None):
            quick_hist = stock.history(period="1d")
            if quick_hist.empty:
                return None, f"Keine Informationen für Ticker '{ticker_symbol}' gefunden (yfinance). Ist der Ticker korrekt?"
            company_name = info.get('symbol', ticker_symbol)
        else:
            company_name = info.get('longName', info.get('shortName', ticker_symbol))
        return {'ticker': ticker_symbol, 'name': company_name, 'info_dict': info}, None
    except Exception as e:
        return None, f"Fehler beim Abrufen der Basisinformationen für '{ticker_symbol}' (yfinance): {str(e)}"

def search_alpha_vantage(keywords):
    """Search for stock symbols using Alpha Vantage API."""
    if not ALPHA_VANTAGE_API_KEY:
        return None, "Alpha Vantage API Key nicht konfiguriert."
    if not keywords:
        return [], None # No keywords, no results, no error

    url = f"https://www.alphavantage.co/query?function=SYMBOL_SEARCH&keywords={keywords}&apikey={ALPHA_VANTAGE_API_KEY}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # Raise an exception for HTTP errors
        data = response.json()
        if "bestMatches" in data:
            # Filter out results that are not Common Stock or ETF, or from non-US exchanges if desired
            # For now, return all matches
            return data["bestMatches"], None
        elif "Note" in data: # API limit reached or other API note
             return None, f"Alpha Vantage API Hinweis: {data.get('Note')}"
        elif "Error Message" in data:
             return None, f"Alpha Vantage API Fehler: {data.get('Error Message')}"
        else:
            return [], None # No matches or unexpected response
    except requests.exceptions.RequestException as e:
        return None, f"Netzwerkfehler bei der Verbindung zu Alpha Vantage: {str(e)}"
    except json.JSONDecodeError:
        return None, "Fehler beim Parsen der Alpha Vantage API Antwort."
    except Exception as e:
        return None, f"Unbekannter Fehler bei der Alpha Vantage Suche: {str(e)}"

def get_stock_detailed_data(ticker_symbol):
    stock_data = {'ticker': ticker_symbol, 'error': None}
    try:
        stock = yf.Ticker(ticker_symbol)
        info = stock.info
        if not info or (info.get('longName') is None and info.get('shortName') is None and info.get('symbol') is None):
            quick_hist = stock.history(period="1d")
            if quick_hist.empty:
                stock_data['error'] = f"Keine detaillierten Informationen für Ticker '{ticker_symbol}' gefunden."
                return stock_data
            stock_data['name'] = info.get('symbol', ticker_symbol) # Fallback to ticker if name is missing
        else:
            stock_data['name'] = info.get('longName', info.get('shortName', ticker_symbol))

        stock_data['info'] = info
        try:
            stock_data['financials_html'] = stock.financials.to_html(classes='table table-sm table-striped table-hover', border=0) if not stock.financials.empty else "Keine Finanzdaten verfügbar."
        except Exception:
            stock_data['financials_html'] = "Finanzdaten konnten nicht geladen werden."

        try:
            stock_data['major_holders_html'] = stock.major_holders.to_html(classes='table table-sm table-striped table-hover', border=0) if stock.major_holders is not None and not stock.major_holders.empty else "Keine Daten zu Haupteignern verfügbar."
        except Exception: stock_data['major_holders_html'] = "Daten zu Haupteignern konnten nicht geladen werden."
        try:
            stock_data['recommendations_html'] = stock.recommendations.tail(5).to_html(classes='table table-sm table-striped table-hover', border=0) if stock.recommendations is not None and not stock.recommendations.empty else "Keine Empfehlungen verfügbar."
        except Exception: stock_data['recommendations_html'] = "Empfehlungen konnten nicht geladen werden."

        quote_info = {
            "Preis": info.get("currentPrice", info.get("regularMarketPrice", "N/A")),
            "Gehandeltes Volumen": info.get("volume", "N/A"),
            "Tageshoch": info.get("dayHigh", "N/A"), "Tagestief": info.get("dayLow", "N/A"),
            "Eröffnung": info.get("open", "N/A"), "Vortagesschluss": info.get("previousClose", "N/A"),
            "Marktkapitalisierung": info.get("marketCap", "N/A"),
            "Dividendenrendite": info.get("dividendYield", "N/A")
        }
        if isinstance(quote_info.get("Marktkapitalisierung"), (int, float)): quote_info["Marktkapitalisierung"] = f"{quote_info['Marktkapitalisierung']:,}"
        if isinstance(quote_info.get("Dividendenrendite"), (int, float)): quote_info["Dividendenrendite"] = f"{quote_info['Dividendenrendite'] * 100:.2f}%"
        stock_data['quote_info'] = quote_info

    except Exception as e:
        stock_data['error'] = f"Allgemeiner Fehler beim Abrufen der Detaildaten für '{ticker_symbol}': {str(e)}"
    return stock_data

def determine_actual_interval_and_period(selected_period, selected_quality):
    actual_period = selected_period
    adjustment_note = None
    if selected_period == "5d":
        if selected_quality == "high": actual_interval = "1m"
        elif selected_quality == "normal": actual_interval = "5m"
        else: actual_interval = "15m"
    elif selected_period == "1mo":
        if selected_quality == "high": actual_interval = "5m"
        elif selected_quality == "normal": actual_interval = "30m"
        else: actual_interval = "1h"
    elif selected_period == "2mo":
        if selected_quality == "high": actual_interval = "15m"  # Beste Qualität für 60 Tage
        elif selected_quality == "normal": actual_interval = "30m"
        else: actual_interval = "1h"
    elif selected_period in ["6mo", "ytd"]:
        if selected_quality == "high": actual_interval = "1h"
        elif selected_quality == "normal": actual_interval = "1d"
        else: actual_interval = "1wk"
    elif selected_period in ["1y", "2y"]:
        if selected_quality == "high": actual_interval = "1d"
        elif selected_quality == "normal": actual_interval = "1wk"
        else: actual_interval = "1mo"
    elif selected_period in ["5y", "max"]:
        if selected_quality == "high": actual_interval = "1wk"
        elif selected_quality == "normal": actual_interval = "1mo"
        else: actual_interval = "3mo"
    else: actual_interval = "1d" # Default

    # Anpassungen basierend auf yfinance Limits für Intervalle
    original_period_for_note = actual_period
    # Für 1 m Intervall: max. 7 Tage, aber yfinance sagt oft 5d sei besser für 1 m.
    # yfinance erlaubt 1 m für bis zu 7 Tage, aber Daten sind intraday und haben nur für 5 Handelstage lückenlos.
    # Für die feinsten Auflösungen:
    if actual_interval == "1m" and actual_period not in ["1d", "2d", "3d", "4d", "5d", "7d"]: # Max 7d for 1m data
        actual_period = "5d" # Sicherer Standard für 1 m
    # Für Intervalle <60m: Daten sind für die letzten 60 Tage verfügbar
    elif actual_interval in ["2m", "5m", "15m", "30m"]:
        # Wenn der ausgewählte Zeitraum länger als 60 Tage ist, wird er auf 60 Tage angepasst.
        # Gültige Perioden für diese Intervalle sind z.B. 1d, 5d, 1mo, 60d.
        if selected_period not in ["1d", "5d", "1mo", "60d"]:
             actual_period = "60d" # yf max 60d
    # Für stündliche Intervalle (1h, 60m, 90m): Daten sind für die letzten 730 Tage (ca. 2 Jahre) verfügbar
    elif actual_interval in ["60m", "90m", "1h"] and actual_period not in ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "ytd", "730d"]:
        if selected_period in ["5y", "max"]: actual_period = "2y" # yf max 730d

    if original_period_for_note != actual_period:
        period_display_original = next((p[1] for p in AVAILABLE_PERIODS if p[0] == original_period_for_note), original_period_for_note)
        period_display_actual = next((p[1] for p in AVAILABLE_PERIODS if p[0] == actual_period), actual_period)
        quality_display = next((q[1] for q in AVAILABLE_QUALITIES if q[0] == selected_quality), selected_quality)
        adjustment_note = (f"Hinweis: Zeitraum für Qualität '{quality_display}' und ursprüngliche Auswahl '{period_display_original}' "
                           f"auf '{period_display_actual}' angepasst, um Intervall '{actual_interval}' zu unterstützen.")
    return actual_period, actual_interval, adjustment_note

def generate_stock_plotly_chart(ticker_symbol, period="1y", interval="1d", quality_note=None, remove_gaps=True, dark_mode=False, show_axis_titles=True, chart_height=None, margin_l=50, margin_r=20, margin_t=80, margin_b=50):
    chart_html = None
    error_msg = quality_note if quality_note else None
    company_name = ticker_symbol

    try:
        stock = yf.Ticker(ticker_symbol)
        info_temp = stock.info
        if info_temp and (info_temp.get('longName') or info_temp.get('shortName')):
            company_name = info_temp.get('longName', info_temp.get('shortName', ticker_symbol))
        elif info_temp and info_temp.get('market') == 'cccrypto_market':
            company_name = info_temp.get('name', company_name)

        hist_data = stock.history(period=period, interval=interval, auto_adjust=True, prepost=False)

        if hist_data.empty:
            current_err = f"Keine Kursdaten für '{ticker_symbol}' mit Periode '{period}' und Intervall '{interval}' gefunden."
            error_msg = (error_msg + " | " if error_msg else "") + current_err
        else:
            font_color = '#cdd3da' if dark_mode else '#1c1e21'
            grid_color = 'rgba(255, 255, 255, 0.1)' if dark_mode else 'rgba(0, 0, 0, 0.1)'

            fig = go.Figure()
            fig.add_trace(go.Candlestick(x=hist_data.index,
                                         open=hist_data['Open'], high=hist_data['High'],
                                         low=hist_data['Low'], close=hist_data['Close'],
                                         name=f'{ticker_symbol}'))

            period_display = next((p[1] for p in AVAILABLE_PERIODS if p[0] == period), period)
            interval_map_for_display = {"1m": "1 Min", "2m": "2 Min", "5m": "5 Min", "15m": "15 Min",
                                        "30m": "30 Min", "60m": "1 Std", "1h": "1 Std", "90m": "90 Min",
                                        "1d": "Täglich", "1wk": "Wöchentlich", "1mo": "Monatlich",
                                        "3mo": "Quartalsweise"}
            interval_display = interval_map_for_display.get(interval, interval)

            title_text = f'Kurs: {company_name} ({ticker_symbol})<br><span style="font-size:0.8em;">Zeitraum: {period_display}, Auflösung: {interval_display}</span>' if show_axis_titles else ''

            # Spezielle Y-Achsen-Einstellungen für Widgets, um Ränder automatisch anzupassen
            yaxis_settings = {
                "gridcolor": grid_color, "linecolor": grid_color, 
                "zeroline": False, "showticklabels": True
            }
            if not show_axis_titles:  # Dies ist ein Widget
                yaxis_settings["automargin"] = True

            fig.update_layout(
                title=title_text,
                xaxis_title='Datum / Uhrzeit' if show_axis_titles else '',
                yaxis_title='Preis' if show_axis_titles else '',
                xaxis_rangeslider_visible=False,
                margin=dict(l=margin_l, r=margin_r, t=margin_t, b=margin_b),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color=font_color),
                xaxis=dict(gridcolor=grid_color, linecolor=grid_color, zeroline=False, showticklabels=False),
                yaxis=yaxis_settings,
                height=chart_height,
                showlegend=False
            )

            if remove_gaps:
                # Lücken für Wochenenden bei täglichen, wöchentlichen, etc. Intervallen entfernen
                if interval in ["1d", "1wk", "1mo", "3mo"]:
                    fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
                # Lücken für Wochenenden UND Nächte bei Intraday-Intervallen entfernen
                elif 'm' in interval or 'h' in interval:
                    fig.update_xaxes(rangebreaks=[
                        dict(bounds=["sat", "mon"]),  # Wochenenden
                        dict(pattern="hour", bounds=[16, 9.5])  # Außerhalb der US-Handelszeiten (angenommen)
                    ])

            # Konfiguration für statische Plots (Widgets) vs. interaktive Plots
            plot_config = {'displayModeBar': False}
            if not show_axis_titles:  # Dies ist ein Widget
                plot_config['staticPlot'] = True
            chart_html = fig.to_html(full_html=False, include_plotlyjs='cdn', config=plot_config)

    except Exception as e:
        exception_str = str(e)
        display_ticker_name = company_name if company_name and company_name != ticker_symbol else ticker_symbol
        current_err_intro = f"Fehler beim Generieren des Charts für '{display_ticker_name}' (Periode: {period}, Intervall: {interval}): "
        if "HTTP Error 404" in exception_str:
            current_err = f"{current_err_intro}Daten nicht gefunden (HTTP 404). Wahrscheinlich ist diese Aktie nicht bei yfinance"
        elif "No data found for this date range" in exception_str or "yfinance failed to decrypt Yahoo data" in exception_str:
            current_err = f"{current_err_intro}Keine Daten für diese Auswahl. Die Kombination ist evtl. ungültig oder der Ticker nicht verfügbar."
        elif "pattern_forms:" in exception_str and "No pattern found for" in exception_str:
            current_err = f"{current_err_intro}Das Tickersymbol '{ticker_symbol}' scheint ungültig oder nicht unterstützt zu sein."
        else:
            current_err = f"{current_err_intro}{exception_str}"
        error_msg = (error_msg + " | " if error_msg and error_msg not in current_err else "") + current_err

    return chart_html, error_msg, company_name


def yfinance_ticker_is_valid(ticker_symbol: str) -> bool:
    """
    Überprüft zuverlässiger, ob ein Ticker auf yfinance gültig ist und Marktdaten hat.
    """
    if not ticker_symbol:
        return False
    try:
        stock = yf.Ticker(ticker_symbol)
        info = stock.info

        # Primärer Check: Ist ein Preis verfügbar? Das ist die wichtigste Bedingung.
        if info.get('regularMarketPrice') is not None or info.get('currentPrice') is not None:
            return True

        # Sekundärer Check: Wenn .info keine Preisdaten liefert (z.B. bei Indizes),
        # prüfen, ob zumindest historische Daten vorhanden sind.
        if 'longName' in info or 'shortName' in info:
            if not stock.history(period="5d", interval="1d").empty:
                return True

        return False
    except Exception:
        # Jede Exception (z.B. HTTP-Fehler bei ungültigen Tickern) bedeutet,
        # dass der Ticker nicht gültig ist.
        return False


def create_portfolio_graph(history_data: list[dict], dark_mode: bool = False, line_strength:int=4) -> str | None:
    if not history_data or len(history_data) < 2:
        return None

    dates = [datetime.fromisoformat(item['date']) for item in history_data]
    net_worths = [item['net_worth'] for item in history_data]
    start_worth = net_worths[0]
    end_worth = net_worths[-1]
    percent_changes = [((val / start_worth) - 1) * 100 for val in net_worths]
    is_gain = end_worth >= start_worth
    bg_color = 'rgba(0,0,0,0)'

    if dark_mode:
        font_color = '#D3D3D3'
        line_color = '#00C805' if is_gain else '#FF4136'
        grid_color = 'rgba(255, 255, 255, 0.1)'
    else:
        font_color = '#444'
        line_color = '#198754' if is_gain else '#dc3545'
        grid_color = 'rgba(230, 230, 230, 0.7)'

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=net_worths, mode='lines',
        line=dict(color=line_color, width=line_strength),
        hoverinfo='y+x', name='Depotwert'
    ))
    fig.add_trace(go.Scatter(
        x=dates, y=percent_changes, yaxis='y2',
        visible=False, hoverinfo='none'
    ))

    fig.update_layout(
        height=250,
        margin=dict(l=50, r=45, t=5, b=20),
        paper_bgcolor=bg_color,
        plot_bgcolor=bg_color,
        font=dict(color=font_color),
        showlegend=False,
        xaxis=dict(
            showgrid=False,
            tickvals=[dates[0], dates[-1]],
            ticktext=[dates[0].strftime('%d. %b'), dates[-1].strftime('%d. %b')],
            zeroline=False
        ),
        yaxis=dict(
            title='', tickprefix='€', gridcolor=grid_color, zeroline=False
        ),
        yaxis2=dict(
            title="", overlaying='y', side='right', showgrid=False,
            ticksuffix='%', tickfont=dict(color=font_color), zeroline=False
        )
    )
    return fig.to_html(full_html=False, include_plotlyjs='cdn', config={'displayModeBar': False})


def get_or_generate_widget_chart(conn, ticker: str, dark_mode: bool) -> str | None:
    """
    Prüft den Cache. Wenn kein gültiger Chart vorhanden ist, wird er generiert, 
    gespeichert und zurückgegeben.
    """
    cursor = conn.cursor()
    twenty_four_hours_ago = datetime.now() - timedelta(hours=24)
    dark_mode_int = int(dark_mode) if dark_mode is not None else 0

    # 1. Cache prüfen
    cursor.execute("""
        SELECT chart_html FROM cached_charts 
        WHERE ticker = ? AND dark_mode = ? AND last_updated > ?
    """, (ticker, dark_mode_int, twenty_four_hours_ago))
    result = cursor.fetchone()
    if result:
        return result[0]

    # 2. Wenn nicht im Cache: Generieren, speichern und zurückgeben
    chart_html, error_msg, _ = generate_stock_plotly_chart(
        ticker_symbol=ticker,
        period="1y",
        interval="1d",
        remove_gaps=True,
        dark_mode=dark_mode,
        show_axis_titles=False,
        chart_height=150,
        margin_l=0, margin_r=30, margin_t=5, margin_b=5
    )

    if chart_html and not error_msg:
        cursor.execute("""
            INSERT OR REPLACE INTO cached_charts (ticker, dark_mode, chart_html, last_updated)
            VALUES (?, ?, ?, ?)
        """, (ticker, dark_mode_int, chart_html, datetime.now()))
        conn.commit()
        return chart_html
    elif error_msg:
        print(f"[Chart-Gen] Fehler beim Generieren des Charts für {ticker}: {error_msg}")
        return None
    return None

def update_popular_charts_cache(conn):
    """
    Holt die beliebtesten Aktien und aktualisiert proaktiv deren Charts im Cache 
    für beide Modi (hell und dunkel).
    """
    print("[Cache-Job] Starte proaktives Update der beliebten Charts...")
    popular_stocks = DepotEndpoint.get_most_popular_stocks(conn)
    if not popular_stocks:
        print("[Cache-Job] Keine beliebten Aktien zum Aktualisieren gefunden.")
        return

    for ticker in popular_stocks.keys():
        print(f"[Cache-Job] Aktualisiere Cache für Ticker: {ticker}")
        # Cache für beide Modi füllen
        get_or_generate_widget_chart(conn, ticker, dark_mode=True)
        get_or_generate_widget_chart(conn, ticker, dark_mode=False)
    print("[Cache-Job] Proaktives Update abgeschlossen.")


@app.route('/', methods=['GET'])
def landing_page():
    # Redirect to search page instead of login if not logged in, or dashboard if logged in
    if 'user_id' in session:
        return redirect(url_for('dashboard_page'))
    return redirect(url_for('search_stock_page'))


@app.route('/dashboard')
@login_required
def dashboard_page():
    conn = get_db()
    user_id = session['user_id']

    depot_data = DepotEndpoint.get_depot_details(conn, user_id)

    if depot_data is None:
        flash("Fehler: Dein Benutzerkonto konnte nicht gefunden werden.", 'error')
        return redirect(url_for('logout'))

    # Platzhalter-Daten für den Graphen
    history_data = LeaderboardEndpoint.fetch_and_group_leaderboard(conn)

    if not session.get('user_id') in history_data.keys():
        LeaderboardEndpoint.insert_current_net_worth_for_user(conn, user_id)
        history_data = LeaderboardEndpoint.fetch_and_group_leaderboard(conn)

    if session.get('user_id') in history_data.keys():
        history_data = history_data[session.get('user_id')]
    else:
        history_data = [
            {"date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'), "net_worth": 50000.0},
            {"date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'), "net_worth": 50000.0},
        ]


    # NEU: Dark-Mode-Status aus dem globalen 'g'-Objekt holen
    dark_mode_status = g.user_settings and g.user_settings.get('dark_mode') == 1

    # Graph-HTML mit der Dark-Mode-Einstellung erstellen
    graph_html = create_portfolio_graph(history_data, dark_mode=dark_mode_status)

    # Die `conn` wird durch @app.teardown_appcontext geschlossen

    return render_template(
        'depot.html',
        depot=depot_data,
        graph_html=graph_html
    )


@app.route('/search')
def search_stock_page():
    query = request.args.get('keywords', '').strip()
    results, error = None, None
    popular_stocks_charts = {}

    conn = get_db()
    dark_mode_status = g.user_settings and g.user_settings.get('dark_mode')

    popular_stocks = DepotEndpoint.get_most_popular_stocks(conn)
    if popular_stocks:
        chart_period = "1y"
        period_display_text = next((p[1] for p in AVAILABLE_PERIODS if p[0] == chart_period), chart_period)

        for ticker, total_value in popular_stocks.items():
            chart_html = get_or_generate_widget_chart(conn, ticker, dark_mode_status)
            basic_info, _ = get_stock_basic_info_yfinance(ticker)
            popular_stocks_charts[ticker] = {
                'chart': chart_html,
                'name': basic_info.get('name', ticker) if basic_info else ticker,
                'period_display': period_display_text,
                'total_value': total_value
            }

    if query:
        if not ALPHA_VANTAGE_API_KEY:
            error = "Suche ist deaktiviert, da der Alpha Vantage API Key fehlt."
        else:
            raw_results, error = search_alpha_vantage(query)
            if raw_results:
                results = []
                for res in raw_results:
                    res['yfinance_valid'] = yfinance_ticker_is_valid(res['1. symbol'])
                    results.append(res)
                results.sort(key=lambda x: x['yfinance_valid'], reverse=True)
            elif not error:
                flash(f"Keine Ergebnisse für '{query}' gefunden.", 'info')

        if error:
            flash(error, 'error')

    return render_template(
            'search_page.html',
            query=query,
            results=results,
            error=error,
            popular_stocks_charts=popular_stocks_charts
        )

@app.route('/trade/<string:ticker_symbol>', methods=['GET', 'POST'])
@login_required
def trade_page(ticker_symbol):
    conn = get_db()
    ticker_symbol = ticker_symbol.upper()
    basic_info, _ = get_stock_basic_info_yfinance(ticker_symbol)

    if not basic_info:
        flash(f"Ticker '{ticker_symbol}' nicht gefunden. Handel nicht möglich.", 'error')
        return render_template('trade_error.html', ticker=ticker_symbol)

    # Schritt 1: Alle Daten für die Anzeige sammeln
    context = {
        "stock": basic_info.get('info_dict'),
        "ticker": ticker_symbol,
        "position": None,
        "absolute_profit_loss": None,
        "relative_profit_loss": None,
        "available_cash": None
    }

    # Verfügbares Kapital berechnen
    total_cash = AccountEndpoint.get_balance(conn, user_id=session['user_id'])
    locked_cash = TradingEndpoint.get_locked_cash(conn, session['user_id'])
    context["available_cash"] = total_cash - locked_cash

    # Depot-Position und potenziellen G/V berechnen
    position = TradingEndpoint.get_user_position(conn, session['user_id'], ticker_symbol)
    if position and position.get('quantity', 0) > 0:
        context["position"] = position
        current_price = basic_info.get('info_dict', {}).get('regularMarketPrice')

        if current_price and position.get('average_purchase_price'):
            avg_price = position['average_purchase_price']
            qty = position['quantity']

            purchase_value = avg_price * qty
            current_value = current_price * qty
            abs_pl = current_value - purchase_value
            context["absolute_profit_loss"] = abs_pl

            if purchase_value > 0:
                rel_pl = (abs_pl / purchase_value) * 100
                context["relative_profit_loss"] = rel_pl

    # Schritt 2: Formular-Absendung verarbeiten
    if request.method == 'POST':
        try:
            order_details = {
                "ticker": ticker_symbol,
                "order_type": request.form['order_type'],
                "quantity": int(request.form['quantity']),
                "limit_price": float(request.form.get('limit_price')) if request.form.get('limit_price') else None,
                "stop_price": float(request.form.get('stop_price')) if request.form.get('stop_price') else None,
            }

            result = TradingEndpoint.place_order(conn, session['user_id'], order_details)

            if result.get('success'):
                conn.commit()
                flash(result.get('message'), 'success')
                return redirect(url_for('my_orders_page'))
            else:
                flash(result.get('message'), 'error')
                return redirect(url_for('trade_page', ticker_symbol=ticker_symbol))

        except (KeyError, ValueError) as e:
            flash(f'Ungültige Eingabe im Formular. Bitte überprüfen Sie Ihre Daten. Fehler: {e}', 'error')
            return redirect(url_for('trade_page', ticker_symbol=ticker_symbol))

    # Schritt 3: Seite bei GET-Request rendern
    return render_template('trade_page.html', **context)


@app.route('/stock/<string:ticker_symbol>')
def stock_detail_page(ticker_symbol):
    ticker_symbol = ticker_symbol.upper()
    stock_details = get_stock_detailed_data(ticker_symbol) # Uses yfinance

    selected_period = request.args.get('period', '1y')
    selected_quality = request.args.get('quality', 'normal')
    # Eine Checkbox ist nur in den request.args, wenn sie angehakt ist.
    remove_gaps_bool = 'remove_gaps' in request.args

    if not any(p[0] == selected_period for p in AVAILABLE_PERIODS): selected_period = '1y'
    if not any(q[0] == selected_quality for q in AVAILABLE_QUALITIES): selected_quality = 'normal'

    actual_period, actual_interval, adjustment_note = determine_actual_interval_and_period(selected_period, selected_quality)

    chart_html, chart_error_msg, _ = generate_stock_plotly_chart(ticker_symbol,
                                                                 period=actual_period,
                                                                 interval=actual_interval,
                                                                 quality_note=adjustment_note,
                                                                 remove_gaps=remove_gaps_bool)

    overall_error = chart_error_msg if chart_error_msg else stock_details.get('error')
    if overall_error and adjustment_note and "Hinweis:" in adjustment_note and "Fehler:" not in adjustment_note:
        # If there's an error but also a non-error adjustment note, prioritize the note if it's just informational
        if not chart_error_msg and not stock_details.get('error'): # if the only "error" is the note
             overall_error = adjustment_note
        elif adjustment_note not in overall_error : # append note if not already part of error
             overall_error = f"{adjustment_note} | {overall_error}"


    return render_template('stock_detail_page.html',
                           ticker=ticker_symbol,
                           details=stock_details,
                           chart_html=chart_html,
                           error=overall_error,
                           current_period=selected_period,
                           current_quality=selected_quality,
                           current_remove_gaps=remove_gaps_bool,
                           available_periods=AVAILABLE_PERIODS,
                           available_qualities=AVAILABLE_QUALITIES)


@app.route('/leaderboard')
def leaderboard_page():
    page = request.args.get('page', 1, type=int)
    if page < 1:
        page = 1
    page_size = 50  # Wie viele Einträge pro Seite angezeigt werden sollen

    conn = get_db()

    paginated_data = LeaderboardEndpoint.get_paginated_leaderboard(conn, page=page, page_size=page_size)

    total_users = LeaderboardEndpoint.count_users(conn)
    total_pages = math.ceil(total_users / page_size)

    conn.close()

    # --- Scheduler-Logik für die Anzeige der nächsten Aktualisierung (wie zuvor besprochen) ---
    update_interval_minutes = 10  # Zeigt auf die nächste durch 10 teilbare Minute
    now = datetime.now()
    minutes_past_hour = now.minute
    updates_past_hour = minutes_past_hour // update_interval_minutes
    next_update_minute = (updates_past_hour + 1) * update_interval_minutes

    if next_update_minute >= 60:
        next_update_time = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    else:
        next_update_time = now.replace(minute=next_update_minute, second=0, microsecond=0)

    return render_template(
        'leaderboard.html',
        leaderboard_data=paginated_data,
        current_page=page,
        total_pages=total_pages,
        next_update_time=next_update_time
    )
#------------

@app.route('/api/refresh-depot', methods=['POST'])
@login_required
def api_refresh_depot():
    now = datetime.now()
    last_refresh_str = session.get('last_depot_refresh')

    if last_refresh_str:
        last_refresh = datetime.fromisoformat(last_refresh_str)
        if (now - last_refresh) < timedelta(seconds=60):
            # Gib eine Fehlermeldung zurück, wenn zu früh aktualisiert wird
            return jsonify({
                "success": False,
                "message": "Bitte warte 60 Sekunden."
            }), 429

    user_id = session['user_id']
    db = get_db()

    # Depot-Aktualisierung im Depot-System aufrufen (Annahme: es gibt eine solche Funktion)
    # Für dieses Beispiel rufen wir einfach get_depot_details auf, um die Logik zu simulieren
    DepotEndpoint.get_depot_details(db, user_id)

    session['last_depot_refresh'] = now.isoformat()
    # Entferne flash() und gib die Nachricht direkt im JSON zurück
    return jsonify({"success": True, "message": "Erfolgreich!"})


@app.route('/my_orders')
@login_required
def my_orders_page():
    db = get_db()
    all_orders = TradingEndpoint.get_user_orders(db, session['user_id'])

    open_orders = [order for order in all_orders if order['status'] == 'OPEN']
    closed_orders = [order for order in all_orders if order['status'] != 'OPEN']

    # Aktuelle Preise für offene Aufträge in einem Batch holen
    prices = {}
    open_tickers = {order['ticker'] for order in open_orders}
    if open_tickers:
        try:
            data = yf.download(list(open_tickers), period="1d", progress=False, auto_adjust=True)['Close']
            if not data.empty:
                latest_prices = data.iloc[-1]
                prices = latest_prices.to_dict()
        except Exception as e:
            print(f"Fehler beim Holen der Kurse für offene Orders: {e}")

    return render_template('my_orders.html', open_orders=open_orders, closed_orders=closed_orders, prices=prices)


@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings_page():
    conn = get_db()
    if request.method == 'POST':
        action = request.form.get('form_action')

        if action == 'update_instagram_link':
            ig_link = request.form.get('ig_link')
            Settings.update_instagram_link(conn, session['user_id'], ig_link)
            flash('Instagram-Link aktualisiert!', 'success')

        elif action == 'delete_instagram_link':
            Settings.update_instagram_link(conn, session['user_id'], None)
            flash('Instagram-Link entfernt!', 'success')

        elif action == 'update_dark_mode':
            dark_mode_on = 'dark_mode' in request.form
            Settings.update_dark_mode(conn, session['user_id'], dark_mode_on)
            # Kein Flash, da die Änderung sofort sichtbar ist

        elif action == 'update_username':
            new_username = request.form.get('new_username')
            change_status = AccountEndpoint.can_change_username(conn, session['user_id'])
            if change_status['can_change']:
                result = AccountEndpoint.update_username(conn, session['user_id'], new_username)
                if result['success']:
                    session['username'] = new_username
                    flash(result['message'], 'success')
                else:
                    flash(result['message'], 'error')
            else:
                flash(f"Du kannst deinen Namen erst wieder am {change_status['next_change_date']} ändern.", 'error')
        
        conn.commit()
        return redirect(url_for('settings_page'))

    # GET Request
    user_settings = Settings.get_settings(conn, session['user_id'])
    change_status = AccountEndpoint.can_change_username(conn, session['user_id'])
    return render_template('settings.html', settings=user_settings, change_status=change_status)


# Neue Route für den Live-Check des Benutzernamens
@app.route('/check_username')
def check_username():
    name = request.args.get('name', '')
    conn = get_db()
    response_data = UTILITIES.is_username_valid(conn, name)
    conn.close()
    return jsonify(response_data)

@app.route('/check_ig_link')
def check_ig_link():
    try:
        link = request.args.get('link', '')
        response_data = UTILITIES.is_ig_link_valid(link)
        return jsonify(response_data)
    except Exception as e:
        print(e)
        return jsonify({'success': False, 'message': str(e)})




if __name__ == '__main__':
    # siehe init_app_data()
    # use_reloader=False ist wichtig, damit der Scheduler nur einmal startet
    app.run(debug=True, use_reloader=False)
