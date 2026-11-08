# Etykiety i klasyfikacja encji

Etykiety w Home Assistant pomagają oddzielić dane pewne od tych, które wymagają
obserwacji lub weryfikacji fizycznej. Integracja **nie tworzy etykiet
automatycznie** — to zalecany zestaw dla konkretnej instalacji.

## Zalecane etykiety

| Etykieta | Znaczenie |
|---|---|
| `Sinum – znane` | Dane potwierdzone przez Sinum lub przez zaobserwowane zachowanie. |
| `Sinum – prawdopodobne` | Wysoka pewność, ale wymaga potwierdzenia fizycznego. |
| `Sinum – nieznane` | Brak podstaw do klasyfikacji. |
| `Sinum – wolny przekaźnik` | Wolne wyjście przekaźnikowe, którym można sterować. |
| `Sinum – termostat` | Termostat wirtualny i jego strefa. |
| `Sinum – harmonogram` | Harmonogram termiczny. |
| `Sinum – alert` | Błąd lub ostrzeżenie urządzenia. |
| `Sinum – diagnostyka` | Online, firmware, sieć i sygnał. |

## Jak klasyfikować przekaźniki

- **Zarządzane przez termostat** (`managed_by_thermostat`) — nie mają osobnych
  switchy. Steruje się nimi przez encję `climate`. Przypisanie do termostatu jest
  znane; fizyczne obciążenie (siłownik, pompa, przekaźnik) często nie jest
  opisane w Sinum — wtedy dodaj `Sinum – prawdopodobne`.
- **Wolne** — mają switch w Home Assistant. Jeśli ich stan nie zmienił się od
  uruchomienia centrali i nie mają pokoju/funkcji w Sinum, oznacz je jako
  `Sinum – wolny przekaźnik` + `Sinum – prawdopodobne` (rezerwa/niepodłączone).
- **Naprawdę nieznane** — brak jakichkolwiek przesłanek; używaj
  `Sinum – nieznane`.

## Przykład użycia

1. Otwórz **Ustawienia → Urządzenia i usługi → Encje**.
2. Wybierz encję i dodaj etykiety.
3. W dashboardzie lub filtrach HA używaj etykiet do wyświetlania tylko
   potwierdzonych danych.

Etykiety nie zmieniają działania integracji ani encji — są wyłącznie warstwą
porządkującą interfejs i automatyzacje.
