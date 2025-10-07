

@app.route('/tree')
def tree_page():

    page_title = data['title']

    # Wir wandeln das Python-Dictionary in einen JSON-String um.
    # Dieser String wird sicher an das Template übergeben.
    tree_json = json.dumps(data, ensure_ascii=False)

    # Wir rendern das 'decision_tree.html'-Template aus dem /templates Ordner.
    return render_template('decision_tree.html', title=page_title, tree_json=tree_json)
data = {
    'title': "bllalsdflall",
    'frage': 'Wie startest du ein neues Projekt?',
    'kurz_frage': 'Projektstart',
    'type': 'einfach',
    'emoji': '🚀',
    'antworten': {
        'Mit einem genauen Plan': {
            'frage': 'Was ist dir wichtiger im Code?',
            'kurz_frage': 'Code-Stil',
            'type': 'einfach',
            'emoji': '🎨🔧',
            'antworten': {
                'Eleganz & Lesbarkeit': {
                    'frage': 'Wie reagierst du auf einen unerwarteten Bug?',
                    'kurz_frage': 'Bug-Reaktion',
                    'type': 'slider',
                    'preset': 'geduldig_hektisch',
                    'emoji': '🐛',
                    'antworten': {
                        '0%': "Python 🐍: Du bleibst ruhig, analysierst elegant und löst das Problem mit einem klaren Schnitt.",
                        '1%-50%': "Swift 🐦: Du gehst methodisch vor, sicher und mit dem Ziel, eine robuste Lösung zu schaffen.",
                        '51%-99%': "Java ☕: Du durchforstest Berge von Stack-Traces, aber deine Ausdauer führt dich zum Ziel.",
                        '100%': "Perl 🐪: Du schreibst schnell einen kryptischen Regex, der das Problem irgendwie... löst."
                    }
                },
                'Performance & Effizienz': {
                    'frage': 'Brauchst du die volle Kontrolle über die Hardware?',
                    'kurz_frage': 'Kontrolle',
                    'type': 'einfach',
                    'emoji': '🔩',
                    'antworten': {
                        'True': "C++ 🐺: Du bist ein Meister der Komplexität, schnell und mächtig, aber nicht zu zähmen.",
                        'False': "Rust 🦀: Du baust sichere, nebenläufige Systeme, die garantiert nicht zusammenbrechen."
                    }
                }
            }
        },
        'Einfach loslegen': {
            'frage': 'Wo fühlst du dich wohler?',
            'kurz_frage': 'Ebene',
            'type': 'einfach',
            'emoji': '🖥️⚙️',
            'antworten': {
                'Im Frontend (was der User sieht)': {
                    'frage': 'Wie wichtig sind dir die neuesten Trends und Frameworks?',
                    'kurz_frage': 'Trends',
                    'type': 'slider',
                    'preset': 'stabil_hip',
                    'emoji': '✨',
                    'antworten': {
                        '0%': "HTML/CSS 🏛️: Du bist das Fundament. Solide, verlässlich und unersetzlich.",
                        '1%-50%': "JavaScript 🦎: Du bist überall, passt dich jeder Umgebung an und hast für alles einen Trick parat.",
                        '51%-99%': "TypeScript 🦉: Du bringst Ordnung und Weitsicht ins Chaos des Frontends.",
                        '100%': "Svelte ☄️: Du bist die Zukunft, schnell, reaktiv und verschwindest fast, nachdem du deine Magie gewirkt hast."
                    }
                },
                'Im Backend (die Logik dahinter)': {
                    'frage': 'Was ist dein Hauptziel?',
                    'kurz_frage': 'Ziel',
                    'type': 'einfach',
                    'emoji': '🎯',
                    'antworten': {
                        'Maximale Skalierbarkeit': "Go 🦦: Du bist pragmatisch, extrem schnell und für die größten Aufgaben gebaut.",
                        'Schnelle Entwicklung': "Ruby 🐈: Du bist elegant, agil und machst das Leben für Entwickler einfach und schön."
                    }
                }
            }
        }
    }
}
