# Hidrolīzes kontrolieris
Raspbery pi programma (vizuālā daļa lielākoties strādā arī uz Windows ja pareizi iestata) lai kontrolētu hidrolīzes iekārtu attālināti.

# Kāpēc?
Šis projekts varētu ļaut kontrolēt hidrolīzes iekārtas (vai, iespējams, citas līdzīgas iekārtas) darbību bez atsevišķas progrmmatūras izmantošanas - caur web interface.
Caur šo interfeisu iespējams novērot iekārtas pašreizējo stāvokli (tikai datus, bez kameras), iestatīt gandrīz jebkuru iekārtas maināmo darbības parametru un apskatīt iepriekšējos datus.

# Izmantotās bibliotēkas
Projektā izmantotas diezgan daudz bibliotēkas lai pilnveidīgi nodrošinātu programmas darbību.
Trīs savstarpēji sasaistītas un svarīgas bibliotēkas ir flask, flask_login un flask_socketio.
  Flask veic web lapas padošanu lietotājam, tās pirmsapstrādi.
  Flask_login ļoti vienkāršoti veic lietotāja autentifikāciju (Šo daļu būtu vai nu stipri jāuzlabo kopējās programmas kodā vai, iespējams, jāizņem pirms palaišanas).
  flask_socketio nodrošina dzīvo datu piegādi web lapai, tieši dzīvo datu lapai lai būtu iespējams redzēt datus reāllaikā.

Mākaslapas pusē arī izmantota Chart.js bibliotēka lai veidotu grafikus.

Tālāk izmantota threading bibliotēka lai nodrošinātu vairāku procesu vienlaicīgu izpildi un, iespējams, mazinātu noslodzi uz atsevišķu kodolu.

Izmantota arī funkcija sleep no bibliotēkas time lai varētu uz laiku "iepauzēt" programmas izpildi.

Tika pielietota arī datetime bibliotēka lai darbotos ar datumiem un laiku.

Pielietota tika arī json biblotēka lai ilglaicīgi saglabātu iestatīumu kopiju diskā.

Tad arī mazāk tika pielietota funkcija listdir un atribūts path no bibliotēkas os, kā arī funkcija getsourcefile no bibliotēkas inspect lai dinamiski noteiktu izpildāmā faila atrašanās vietu un varētu nosūtīt failu caur web lapu.

Pēdējā bibliotēka ir lgpio, tā strādā tikai uz paša Raspberry Pi (iespējams arī uz citiem līdzīgiem risinājumiem), caur to tiek nodrošināta saziņa ar fiziskajām izejām. Tās darbība noklusējumā ir atslēgta pirmajā app.py rindā.


Programmu vēlams palaizt atsevišķā venv vidē, laba pamācība atrodama šeit: https://dev.to/mursalfk/setup-flask-on-windows-system-using-vs-code-4p9j
