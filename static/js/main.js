document.addEventListener('DOMContentLoaded', () => {

    // NEUE HILFSFUNKTION: Erzeugt einen eindeutigen String-Bezeichner aus einem Karten-Objekt.
    // Dies ist nützlich für Vergleiche und als Schlüssel im DOM (z.B. für Drag & Drop).
    function getCardIdentifier(cardObject) {
    if (cardObject.is_hund) return "Hund";
    if (cardObject.is_phoenix) return "Phoenix";
    if (cardObject.is_drache) return "Drache";
    return `${cardObject.string}-${cardObject.color}`;
}

    // VERALTET: Die Funktion parseCardId wird nicht mehr benötigt, da der Server ganze Objekte schickt.
    // function parseCardId(cardId) { ... }

    // --- Verbindung zum Server herstellen ---
    const socket = io();
    let myPlayerId = null; // Wird vom Server zugewiesen
    let gameStateCache = { played_cards: [] }; // Ein Cache für den letzten bekannten Spielzustand

    // --- DOM-Elemente holen ---
    const sendButton = document.getElementById('send-button');
    const messageArea = document.getElementById('message-area');
    const playArea = document.getElementById('play-area');
    const playerHand = document.getElementById('player-hand');
    const playerIdDisplay = document.getElementById('player-id-display');

    // --- Drag & Drop Logik (angepasst für neue Bezeichner) ---
    function addDragAndDropHandlers() {
        const cards = document.querySelectorAll('.card');
        const dropZones = [playArea, playerHand];

        cards.forEach(card => {
            // Nur die eigenen Karten sollen ziehbar sein!
            if (card.parentElement.id === 'player-hand') {
                card.setAttribute('draggable', 'true');
                card.addEventListener('dragstart', (e) => {
                    // Wir übertragen den eindeutigen Bezeichner der Karte.
                    e.dataTransfer.setData('text/plain', card.dataset.cardId);
                    setTimeout(() => card.classList.add('dragging'), 0);
                });
                card.addEventListener('dragstart', (e) => {
                e.dataTransfer.setData('text/plain', card.dataset.cardId);
                card.classList.add('dragging'); // Klasse sofort hinzufügen
            });
            } else {
                card.setAttribute('draggable', 'false');
            }
        });

        // Drop-Logik bleibt unverändert, da sie mit dem Bezeichner arbeitet.
        dropZones.forEach(zone => {
            zone.addEventListener('dragover', (e) => {
                e.preventDefault();
                zone.classList.add('drag-over');
            });
            zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
            zone.addEventListener('drop', (e) => {
                e.preventDefault();
                zone.classList.remove('drag-over');
                const cardId = e.dataTransfer.getData('text/plain');
                const draggableElement = document.querySelector(`.card.dragging[data-card-id="${cardId}"]`);
                if (draggableElement) {
                    zone.appendChild(draggableElement);
                }
            });
        });
    }

    // --- UI Update Funktion (stark überarbeitet) ---
    // Zeichnet die UI komplett neu basierend auf dem globalen game_state vom Server
    function updateUI(state) {
        // 1. Nachricht aktualisieren
        messageArea.innerHTML = `<p>${state.message}</p>`;

        // Funktion, um ein Karten-Element aus einem Karten-OBJEKT zu erstellen
        const createCardElement = (cardObject) => {
            const cardElement = document.createElement('div');
            cardElement.className = 'card';

            // Wichtige Daten für die Spiel-Logik beibehalten
            cardElement.dataset.cardId = getCardIdentifier(cardObject); // getCardIdentifier wird weiterhin benötigt
            cardElement.dataset.cardObject = JSON.stringify(cardObject);

            // NEUE LOGIK: Farbe direkt als data-Attribut setzen
            // Z.B. erzeugt { color: "red" } -> <div data-color="red">
            if (cardObject.color) {
                cardElement.dataset.color = cardObject.color;
            }

            // NEUE LOGIK: Sonderkarten bekommen ein "data-special" Attribut
            // Das ist sauberer als viele einzelne data-is_drache etc.
            if (cardObject.is_drache) cardElement.dataset.special = 'drache';
            if (cardObject.is_phoenix) cardElement.dataset.special = 'phoenix';
            if (cardObject.is_hund) cardElement.dataset.special = 'hund';
            if (cardObject.is_eins) cardElement.dataset.special = 'eins';


            // NEUE LOGIK: Zeige immer den "string" aus dem Objekt an
            // Die alte HTML-Struktur mit "oben" und "unten" wird vereinfacht.
            cardElement.innerHTML = `<div class="mitte">${cardObject.string}</div>`;

            return cardElement;
        };

        // 2. Ablagebereich (gespielte Karten) aktualisieren
        playArea.innerHTML = '';
        state.played_cards.forEach(cardObj => {
            const cardElement = createCardElement(cardObj);
            playArea.appendChild(cardElement);
        });

        // 3. Eigene Hand aktualisieren
        playerHand.innerHTML = '';
        const myHandCards = state.player_hands[myPlayerId] || [];
        myHandCards.forEach(cardObj => {
            const cardElement = createCardElement(cardObj);
            playerHand.appendChild(cardElement);
        });

        // 4. Drag&Drop-Handler für die neu erstellten Karten registrieren
        addDragAndDropHandlers();
    }


    // --- Socket.IO Event Listener ---

    // Wird einmalig aufgerufen, wenn der Server uns eine ID zuweist
    socket.on('assign_player_id', (data) => {
        myPlayerId = data.player_id;
        playerIdDisplay.textContent = `Du bist: ${myPlayerId}`;
    });

    // Dies ist der wichtigste Listener: Er reagiert auf JEDE Zustandsänderung
    // Der alte, doppelte Listener wurde entfernt und die Logik hier zusammengefasst.
    socket.on('update_state', (newGameState) => {
        console.log("Neuer Spielzustand erhalten:", newGameState);
        // Halte den Cache immer aktuell, damit wir wissen, was vorher war.
        gameStateCache = newGameState;
        updateUI(newGameState);
    });

    // Falls das Spiel voll ist
    socket.on('game_full', (data) => {
        alert(data.message);
        document.body.innerHTML = `<h1>${data.message}</h1>`;
    });


    // --- Client-Aktion: Karten an den Server senden (Logik angepasst) ---
    sendButton.addEventListener('click', () => {
        // 1. Hole alle Karten, die sich aktuell im Ablagebereich befinden.
        const cardsInPlayArea = Array.from(playArea.querySelectorAll('.card'));
        const currentIdentifiersInPlay = cardsInPlayArea.map(card => card.dataset.cardId);

        // 2. Hole die Bezeichner der Karten, die schon VOR diesem Zug im Ablagebereich lagen (aus unserem Cache).
        const previousIdentifiersInPlay = gameStateCache.played_cards.map(cardObj => getCardIdentifier(cardObj));

        // 3. Finde die Bezeichner der Karten, die in diesem Zug NEU hinzugekommen sind.
        const newlyPlayedIdentifiers = currentIdentifiersInPlay.filter(id => !previousIdentifiersInPlay.includes(id));

        // 4. Finde die vollständigen Karten-Objekte, die zu diesen neuen Bezeichnern gehören.
        const cardsToSend = cardsInPlayArea
            .filter(card => newlyPlayedIdentifiers.includes(card.dataset.cardId))
            .map(card => JSON.parse(card.dataset.cardObject)); // Wandle den JSON-String zurück in ein Objekt

        if (cardsToSend.length > 0) {
            console.log('Sende Karten zum Server:', cardsToSend);
            socket.emit('play_cards', { played_cards: cardsToSend });
        } else {
            console.log('Keine neuen Karten im Ablagebereich zum Senden.');
        }
    });
});