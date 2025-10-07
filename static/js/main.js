document.addEventListener('DOMContentLoaded', () => {

    // --- Verbindung zum Server herstellen ---
    const socket = io();
    let myPlayerId = null; // Wird vom Server zugewiesen

    // --- DOM-Elemente holen ---
    const sendButton = document.getElementById('send-button');
    const messageArea = document.getElementById('message-area');
    const playArea = document.getElementById('play-area');
    const playerHand = document.getElementById('player-hand');
    const playerIdDisplay = document.getElementById('player-id-display');

    // --- Drag & Drop Logik (bleibt größtenteils gleich) ---
    function addDragAndDropHandlers() {
        const cards = document.querySelectorAll('.card');
        const dropZones = [playArea, playerHand];

        cards.forEach(card => {
            // Nur die eigenen Karten sollen ziehbar sein!
            if (card.parentElement.id === 'player-hand') {
                card.setAttribute('draggable', 'true');
                card.addEventListener('dragstart', (e) => {
                    e.dataTransfer.setData('text/plain', card.dataset.cardId);
                    setTimeout(() => card.classList.add('dragging'), 0);
                });
                card.addEventListener('dragend', () => {
                    card.classList.remove('dragging');
                });
            } else {
                 card.setAttribute('draggable', 'false');
            }
        });

        // Drop-Logik nur für den Ablagebereich und die eigene Hand
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

    // --- UI Update Funktion (neu) ---
    // Zeichnet die UI komplett neu basierend auf dem globalen game_state vom Server
    function updateUI(state) {
        // 1. Nachricht aktualisieren
        messageArea.innerHTML = `<p>${state.message}</p>`;

        // 2. Ablagebereich aktualisieren
        playArea.innerHTML = '';
        state.played_cards.forEach(cardId => {
            const cardElement = document.createElement('div');
            cardElement.className = 'card';
            cardElement.dataset.cardId = cardId;
            cardElement.innerText = cardId;
            playArea.appendChild(cardElement);
        });

        // 3. Eigene Hand aktualisieren
        playerHand.innerHTML = '';
        const myHandCards = state.player_hands[myPlayerId] || [];
        myHandCards.forEach(cardId => {
            const cardElement = document.createElement('div');
            cardElement.className = 'card';
            cardElement.dataset.cardId = cardId;
            cardElement.innerText = cardId;
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
    socket.on('update_state', (newGameState) => {
        console.log("Neuer Spielzustand erhalten:", newGameState);
        updateUI(newGameState);
    });

    // Falls das Spiel voll ist
    socket.on('game_full', (data) => {
        alert(data.message);
        document.body.innerHTML = `<h1>${data.message}</h1>`;
    });


    // --- Client-Aktion: Karten an den Server senden ---
    sendButton.addEventListener('click', () => {
        const cardsInPlayArea = playArea.querySelectorAll('.card');

        // Finde heraus, welche Karten aus der Hand in den Ablagebereich gezogen wurden
        const playedCardIds = [];
        const myHandCards = Array.from(playerHand.children).map(c => c.dataset.cardId);

        cardsInPlayArea.forEach(cardOnPile => {
            // Eine Karte gilt als gespielt, wenn sie sich im Ablagebereich befindet
            // und NICHT mehr zu den ursprünglichen Karten auf der Hand gehört.
            // Diese Logik ist für dieses UI-Modell ausreichend.
             playedCardIds.push(cardOnPile.dataset.cardId);
        });

        // Filtere Duplikate, die schon vorher da lagen
        const cardsFromThisTurn = playedCardIds.filter(card => !game_state_cache.played_cards.includes(card));

        if(cardsFromThisTurn.length > 0){
             console.log('Sende Karten zum Server:', cardsFromThisTurn);
             socket.emit('play_cards', { played_cards: cardsFromThisTurn });
        } else {
             console.log("Keine neuen Karten im Ablagebereich zum Senden.");
        }
    });

    // Ein kleiner Cache, um zu wissen, welche Karten schon vorher auf dem Stapel lagen
    let game_state_cache = { played_cards: [] };
    socket.on('update_state', (newGameState) => {
        game_state_cache = newGameState; // Cache immer aktuell halten
        updateUI(newGameState);
    });

});