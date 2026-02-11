from dataclasses import dataclass
from typing import List, Optional

@dataclass
class TichuCard:
    suit: Optional[str]  # Jade, Swords, Pagodas, Stars, or None for special cards
    value: str # 2-10, J, Q, K, A, or MahJong, Dog, Phoenix, Dragon
    score: int

class TichuGame:
    def __init__(self):
        self.special_cards = {
            "MahJong": 1,
            "Dog": 0,
            "Phoenix": -25,
            "Dragon": 25
        }
        self.suits = ["Jade", "Swords", "Pagodas", "Stars"]
        self.values = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
        
    def parse_card(self, card_str: str) -> TichuCard:
        """
        Versucht, einen Karten-String zu parsen.
        Erwartetes Format z.B. "Jade 2", "Swords A", "Dragon"
        """
        parts = card_str.split()
        
        if len(parts) == 1:
            name = parts[0]
            if name in self.special_cards:
                return TichuCard(suit=None, value=name, score=self.special_cards[name])
        
        if len(parts) == 2:
            suit, value = parts
            if suit in self.suits and value in self.values:
                score = 0
                if value == "5": score = 5
                if value == "10": score = 10
                if value == "K": score = 10
                return TichuCard(suit=suit, value=value, score=score)
                
        raise ValueError(f"Ungültige Karte: {card_str}")

    def process_cards(self, cards_data: List[str]) -> dict:
        """
        Nimmt eine Liste von Karten-Strings entgegen und gibt das Ergebnis zurück.
        """
        parsed_cards = []
        errors = []
        total_score = 0
        
        for card_str in cards_data:
            try:
                card = self.parse_card(card_str)
                parsed_cards.append({
                    "suit": card.suit,
                    "value": card.value,
                    "score": card.score
                })
                total_score += card.score
            except ValueError as e:
                errors.append(str(e))
        
        return {
            "success": len(errors) == 0,
            "parsed_cards": parsed_cards,
            "total_score": total_score,
            "errors": errors
        }
