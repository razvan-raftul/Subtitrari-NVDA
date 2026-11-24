# Subtitrări în română – add-on pentru NVDA

Făcut pe 29 octombrie 2026, la cererea lui Răzvan. Pentru Claude: citește tot înainte să faci ceva și nu modifica nimic fără indicația lui Răzvan. Răspunsuri scurte, în română vorbită, fără liste cu buline.

## Ce face
Citește singur subtitrările afișate pe ecran, din orice program (browser, YouTube, Netflix, VLC), și le traduce în română dacă sunt în altă limbă.
La fiecare jumătate de secundă recunoaște textul din partea de jos a ferestrei din față (OCR-ul Windows, același ca NVDA+R). Când apare o replică nouă și rămâne la fel două citiri la rând, o traduce (Google Translate, cu internet) și o spune, întrerupând ce spunea NVDA înainte. Aceeași replică nu se repetă cât stă pe ecran.

## Taste
NVDA+Alt+V (din 1.1.0): ascultă vocea personajelor și o spune tradusă în română (vezi mai jos).
NVDA+Alt+S: pornește și oprește citirea subtitrărilor (se ține minte și după repornirea NVDA). Traducerea e mereu pornită (o replică deja în română se spune cum e), iar zona e mereu partea de jos a ferestrei. Răzvan a cerut (29 oct.) o singură tastă, fără alte opțiuni.
Tasta se poate schimba din NVDA, Preferințe, Gesturi de intrare, categoria „Subtitrări în română”.

## Viteza (29 oct., cerut de Răzvan: cât mai repede)
Citește ecranul la fiecare 250 ms. O replică nouă pleacă la tradus din prima citire, iar cât se traduce se verifică încă o citire că a rămas la fel; așa traducerea e de obicei gata când replica e confirmată. Traducerea folosește o conexiune ținută deschisă la translate.googleapis.com (fără o nouă legătură la fiecare replică). În mod obișnuit replica se aude la mai puțin de o secundă după ce apare.

## Nu se mai pierd replici (29 oct., Răzvan: „citește doar o parte”)
Cauzele găsite: o replică nouă tăia vorbirea celei de dinainte (cancelSpeech); dacă traducerea unei replici întârzia și venea alta, prima nu se mai spunea deloc; la subtitrările care curg (YouTube automat) textul se schimba puțin câte puțin și era luat drept aceeași replică.
Acum replicile confirmate intră într-o coadă și se spun toate, în ordine, una după alta, fără să se întrerupă (_coada, _goleste). La subtitrările care curg se spun doar cuvintele noi (parte_noua). Zona e jumătatea de jos a ferestrei (de la 55% în jos), ca să încapă și subtitrările pe două rânduri.

## Nimic sărit (29 oct., Răzvan: „asigură-te că nu mai sare nimic”)
O replică văzută o singură dată (a stat sub jumătate de secundă) se spune și ea când dispare sau vine alta, afară de cazul în care e doar o bucată din replica de dinainte sau de după (când apare sau dispare treptat, _abandon, _cuprinsa).
Comparația lucrează pe rânduri (OCR-ul dă rândurile): la subtitrările care curg se spune doar rândul sau cuvintele noi; o replică normală se spune întreagă, chiar dacă seamănă cu cea de dinainte („Yes, I know.” apoi „I know!”). Două citiri sunt „aceeași replică” doar dacă seamănă peste 90%.
Proba: o simulare cu 120 de replici, cu greșeli de recunoaștere, apariții și dispariții treptate, replici foarte scurte și traduceri care vin în altă ordine; pe 8 rulări nu s-a pierdut nicio replică. Uneori se mai spune o replică de două ori, când recunoașterea o citește foarte diferit. Scriptul probei e în Cod sursa\proba_simulare.py (cere stub-urile din sesiunea lui Claude, nu merge singur).
Ce nu se poate garanta: subtitrări greu de citit pentru OCR (pe fundal de aceeași culoare, scris foarte mic) și cele care stau pe ecran mai puțin de un sfert de secundă. Dacă apeși o tastă, NVDA oprește ce spune, inclusiv replicile din coadă.

## Vocea personajelor (versiunea 1.1.0, 29 oct. 2026, cerut de Răzvan; are Windows 11)
NVDA+Alt+V pornește și oprește. Pornește singur Subtitrările live din Windows 11 (LiveCaptions.exe), care transformă în text tot ce se aude pe calculator, și le închide la oprire dacă le-a pornit el. Add-on-ul citește textul lor la fiecare 150 ms (UI Automation, elementul CaptionsTextBlock din fereastra LiveCaptionsDesktopWindow), ia propozițiile terminate care n-au mai fost (aliniate cu citirea de dinainte, ca să nu se repete și să nu se sară) și le trimite la tradus și spus, prin aceeași coadă ca subtitrările. O propoziție neterminată care nu se mai schimbă o secundă (vorbitorul face pauză) se spune oricum, iar când se termină se spune doar restul. Ce era deja în fereastră la pornire nu se citește. Codul e în voce.py.
NVDA+Alt+S și NVDA+Alt+V nu merg deodată: pornind unul se oprește celălalt. Ce e pornit se ține minte și după repornirea NVDA.
Întârzierea: Subtitrările live scriu cu vreo jumătate de secundă–o secundă după vorbă, plus terminarea propoziției și traducerea; de obicei 1–2 secunde.
Prima dată, Windows poate cere descărcarea limbii pentru Subtitrările live (un buton Continuare/Descărcare în fereastra lor). Limba recunoscută e cea aleasă acolo (din start engleza).
Netestat încă pe calculatorul lui Răzvan.

## Versiunea 1.1.1 (29 oct., Răzvan: „a citit o dată «Pauză 00» și apoi nimic”, pe alt laptop)
Cauza probabilă: pe film fundalul se schimbă și recunoașterea dă de fiecare dată un text puțin diferit; comparația literă cu literă (peste 90%) nu le lua drept aceeași replică, deci nicio replică nu era confirmată, iar la înlocuire era luată drept „bucată din următoarea” și sărită. Acum două citiri sunt aceeași replică și dacă cel puțin 80% din cuvinte se potrivesc în ambele sensuri (_la_fel; cuvintele se potrivesc cu greșeli mici doar de la 4 litere în sus, ca „are” și „were” să rămână diferite). Simularea cu greșeli la fiecare citire: nicio replică pierdută, unele spuse de două ori.
Fiecare text nou recunoscut se scrie în jurnalul NVDA („subtitrari: citit ...”), ca să se vadă ce vede add-on-ul dacă tot nu citește.

## Fișiere
subtitrariRomana.nvda-addon: add-on-ul (se instalează cu Enter pe el).
Cod sursa: manifest.ini și globalPlugins\subtitrariRomana (__init__.py: subtitrările de pe ecran și coada de traducere; voce.py: vocea, prin Subtitrările live; actualizare.py: actualizarea automată).
Add-on-ul e o arhivă zip cu manifest.ini și globalPlugins.

## Actualizare automată
La pornirea NVDA, după 20 de secunde, citește version.txt din release-ul „latest” al depozitului GitHub razvan-raftul/Subtitrari-NVDA. Dacă e mai nou, NVDA spune doar „Se actualizează” și procentul, instalează, spune „100 la sută. Actualizare terminată.” și repornește NVDA.
Depozitul nu e făcut încă (de întrebat pe Răzvan); până atunci actualizarea doar nu găsește nimic și tace.

## Limite
Subtitrările care sunt text (YouTube, Netflix în browser) și cele arse în imagine se citesc la fel, prin OCR. Merge și cu perdeaua de ecran pornită pe NVDA nou (2025 și mai nou, captura WGC); pe NVDA mai vechi perdeaua trebuie oprită.
OCR-ul folosește limba aleasă în NVDA la Recunoașterea Windows OCR; dacă subtitrările sunt în altă limbă cu alt alfabet, limba aceea trebuie aleasă acolo.
Uneori prinde și texte din player (titlul, butoanele) când apar jos.
Netestat încă pe calculatorul lui Răzvan.


## Actualizare automată (24 nov. 2026, cerut de Răzvan)
- Depozitul public github.com/razvan-raftul/Subtitrari-NVDA (codul în addon/, workflow în .github/workflows/build.yml). Fiecare push pe main face addonul, cu versiunea 1.2.<numărul build-ului>, și îl pune în release-ul „latest” cu version.txt.
- actualizare.py: la 20 de secunde după pornirea NVDA citește version.txt; dacă e mai nouă, descarcă și instalează. NVDA spune doar procentul din 10 în 10, cu bipurile de progres, apoi repornește.
- Codul de lucru e în depozit; modificările se urcă cu git push din sesiune.
