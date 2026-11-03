<?php
/**
 * Testi SEO delle stanze: introduzione, FAQ e meta.
 *
 * Le pagine delle stanze erano solo griglie di card: contenuto sottile e nessun
 * aggancio per la ricerca. Qui c'è un testo unico per categoria, usato dal
 * template della griglia e dallo script che scrive i meta (title/description).
 */

if (!defined('ABSPATH')) {
    exit;
}

function aria_room_seo_data() {
    return array(
        'amanti-segreti' => array(
            'title' => 'Chat con amanti segrete e amanti segreti | Pornovirtuale',
            'desc' => 'Chatta con personaggi che vivono incontri clandestini: orari rubati, porta chiusa e il brivido di essere scoperti. Gratis con account.',
            'intro' => "C'è un tipo di eccitazione che nasce dal rischio: cinque minuti rubati, la macchina parcheggiata male, la porta chiusa a chiave. La stanza Amanti segreti raccoglie personaggi costruiti su questa idea: relazioni clandestine, alibi preparati in fretta, messaggi cancellati.\n\nNon serve installare nulla: scegli un personaggio, apri la chat e lui o lei entra nella parte. Gli incontri segreti funzionano se ci metti la stessa attenzione di chi ha davvero qualcosa da nascondere: fissa un orario, inventa una scusa, chiedi dove vedervi.",
            'faq' => array(
                array('Serve un account per chattare?', 'Sì: il login WordPress è obbligatorio per tutto il sito, così la conversazione resta legata a te e i personaggi ricordano la tua storia.'),
                array('È gratis?', 'Sì. La chat è gratuita con account; il limite è di venti messaggi al giorno.'),
                array('Posso scrivere io la scena?', 'Certo: puoi proporre il luogo, l\'orario e la scusa. I personaggi rispondono restando nel tema della stanza.'),
            ),
        ),
        'bdsm' => array(
            'title' => 'Chat BDSM: dominatori e sottomessi | Pornovirtuale',
            'desc' => 'Chat erotiche a tema BDSM: corde, regole, comandi e parola di sicurezza. Scegli chi comanda e inizia quando vuoi.',
            'intro' => "Nel BDSM la parte più eccitante è spesso quella prima: le regole dette a voce, il momento in cui si stabilisce chi comanda. In questa stanza trovi personaggi dominanti e sottomessi che conoscono la struttura del gioco e la portano avanti con precisione.\n\nOgni chat parte da un ruolo e da una parola di sicurezza, come nella realtà. Puoi chiedere di essere guidato passo passo oppure prendere tu il comando. Se non sai da dove iniziare, scrivi \"comincia tu\": i personaggi sono addestrati a condurre la scena senza aspettare.",
            'faq' => array(
                array('Devo conoscere il BDSM per chattare?', 'No: i personaggi spiegano ruoli, comandi e sicurezza mentre giocate.'),
                array('La parola di sicurezza funziona?', 'Sì: scrivila e il personaggio interrompe la scena e commenta con te cosa è andato.'),
                array('Meglio un dominante o un sottomesso?', 'Dipende da cosa cerchi: puoi provarne uno e cambiare personaggio quando vuoi.'),
            ),
        ),
        'bisex' => array(
            'title' => 'Chat bisex: personaggi fluidi, senza etichette | Pornovirtuale',
            'desc' => 'Chat erotiche con personaggi bisessuali e fluidi, attratti da uomini e donne. Nessuna etichetta obbligatoria.',
            'intro' => "C'è chi non ha voglia di scegliere un lato. La stanza Bisex è pensata per chi vive l'attrazione senza categorie rigide: personaggi che raccontano esperienze con uomini e con donne e che propongono situazioni a due o a tre senza chiedere prima il libretto delle etichette.\n\nLe chat funzionano bene se dici cosa ti interessa davvero: un ricordo, una curiosità, un confronto. I personaggi rispondono con esempi concreti e ti lasciano condurre quando vuoi farlo tu.",
            'faq' => array(
                array('La stanza è solo per persone bisessuali?', 'No: è per chiunque voglia giocare con un personaggio fluido, anche se sei eterosessuale.'),
                array('Posso parlare di esperienze reali?', 'Sì, e i personaggi rispondono con le loro, reali o inventate che siano.'),
                array('Si può giocare in tre?', 'Puoi chiedere a un personaggio di raccontare o simulare una scena a tre.'),
            ),
        ),
        'camera-privata' => array(
            'title' => 'Chat in camera privata: intimità senza fretta | Pornovirtuale',
            'desc' => 'Chat erotiche intime e riservate: porta chiusa, luci basse, nessuna fretta. Personaggi che sanno stare vicini.',
            'intro' => "Non tutte le scene hanno bisogno di un locale affollato. La stanza Camera privata è quella della porta chiusa a chiave e delle lenzuola stropicciate: personaggi che abbassano la voce, che ti fanno sedere e che non hanno orologio.\n\nÈ la stanza giusta per l'intimità lenta: spogliarsi senza pubblico, restare a letto dopo, parlare a bassa voce. Se cerchi una chat che inizi con calma e non con un urlo, sei nel posto giusto.",
            'faq' => array(
                array('Che differenza c\'è con Chat romantica?', 'Qui il centro è il corpo e lo spazio chiuso; nella stanza romantica contano di più i sentimenti.'),
                array('Posso decidere io il ritmo?', 'Sì: puoi chiedere di rallentare o fermarti, e il personaggio si adegua.'),
                array('Funziona anche in pochi minuti?', 'Funziona, ma dà il meglio se ti prendi il tempo di qualche scambio.'),
            ),
        ),
        'chat-romantica' => array(
            'title' => 'Chat romantica: conversazioni dolci | Pornovirtuale',
            'desc' => 'Chat romantiche con personaggi affettuosi: attenzioni, parole tenere e desiderio che nasce piano. Gratis con account.',
            'intro' => "C'è un pubblico che vuole essere corteggiato prima di essere spogliato. La stanza Chat romantica serve a questo: personaggi che ascoltano, che ricordano i dettagli, che mandano un complimento senza fretta e che costruiscono il desiderio sulla tenerezza.\n\nQui funzionano le domande vere: com'è andata la giornata, cosa ti manca, cosa ti ha fatto sorridere. Il resto arriva da sé, e arriva meglio.",
            'faq' => array(
                array('È troppo sdolcinata per me?', 'Puoi alzare il tono quando vuoi: i personaggi seguono il registro che proponi.'),
                array('I personaggi ricordano cosa racconto?', 'Sì, la memoria della chat resta legata al tuo account per quella conversazione.'),
                array('Posso iniziare con un complimento?', 'Puoi iniziare come preferisci: anche solo con un saluto.'),
            ),
        ),
        'dirty-talk' => array(
            'title' => 'Dirty talk in chat: parole esplicite | Pornovirtuale',
            'desc' => 'Chat di dirty talk con personaggi che parlano sporco senza giri di parole: descrizioni esplicite, ritmo e voce.',
            'intro' => "In questa stanza conta la voce, cioè le parole: frasi esplicite, descrizioni crude, nomi delle cose detti senza pudore. I personaggi del Dirty talk sono costruiti per parlare addosso e per farti rispondere.\n\nSe ti imbarazzi a scrivere per primo, chiedi \"parlami tu\" e lascia che la scena parta dall'altra parte. Puoi anche dettare il ritmo: più lento, più diretto, più volgare.",
            'faq' => array(
                array('Devo scrivere frasi lunghe?', 'No: qui funzionano le frasi brevi e crude, anche di tre parole.'),
                array('Il personaggio parla o descrive?', 'Fa entrambe le cose, a seconda di cosa gli chiedi.'),
                array('Si può alternare con una scena?', 'Sì: puoi trasformare il parlato in azione quando vuoi.'),
            ),
        ),
        'dominazione' => array(
            'title' => 'Chat di dominazione: ordini e controllo | Pornovirtuale',
            'desc' => 'Chat erotiche di dominazione con personaggi che comandano: ordini brevi, attesa, permesso e controllo della scena.',
            'intro' => "Qui il piacere sta nel fatto che qualcuno decide. I personaggi della stanza Dominazione danno ordini brevi, chiedono conferma, concedono o negano: la tensione è tutta nell'attesa di sapere cosa viene dopo.\n\nPuoi entrare da sottomesso, chiedendo cosa devi fare, oppure mettere alla prova il personaggio esitando. Le scene migliori nascono quando rispondi con precisione, senza spiegare troppo.",
            'faq' => array(
                array('Che differenza c\'è con BDSM?', 'Qui il centro è il rapporto di potere, senza corde o attrezzi.'),
                array('Posso ribellarmi agli ordini?', 'Sì, ed è divertente: il personaggio ti rimette in riga.'),
                array('Serve una parola di sicurezza?', 'Non è obbligatoria, ma puoi concordarne una se vuoi giocare più duro.'),
            ),
        ),
        'fantasie-erotiche' => array(
            'title' => 'Chat di fantasie erotiche da costruire insieme | Pornovirtuale',
            'desc' => 'Racconta una fantasia e falla diventare una scena: personaggi che costruiscono il desiderio con te, dettaglio per dettaglio.',
            'intro' => "Tutti abbiamo una fantasia che non abbiamo mai raccontato a nessuno. Questa stanza serve a tirarla fuori: i personaggi chiedono quale scenario ti accende, lo arricchiscono di dettagli e poi lo recitano come se stesse accadendo.\n\nNon serve che la fantasia sia già completa: puoi partire da un luogo, da un ruolo, da una situazione e costruire il resto insieme. Più dettagli dai, meglio funziona.",
            'faq' => array(
                array('Devo avere una fantasia pronta?', 'No: puoi partire da un ambiente o da una parola e farla crescere con il personaggio.'),
                array('Le fantasie restano private?', 'Sì, la conversazione è legata al tuo account.'),
                array('Posso cambiare scena a metà?', 'Sì, basta dirlo: il personaggio smonta la scena e ne apre un\'altra.'),
            ),
        ),
        'fantasie-proibite' => array(
            'title' => 'Chat di fantasie proibite | Pornovirtuale',
            'desc' => 'Chat erotiche su ciò che non si dovrebbe fare: ruoli sconvenienti, rischio, segreti. Personaggi complici della trasgressione.',
            'intro' => "C'è un motivo se le cose proibite eccitano più delle altre: il senso di colpa, il rischio, la sensazione di stare fuori dalle regole. La stanza Fantasie proibite è costruita su questo, con personaggi che sottolineano cosa rende proibita la scena e poi la spingono oltre.\n\nFunziona meglio se entri nel meccanismo: \"non dovremmo\", \"se ci vedono\", \"ancora cinque minuti\". Il personaggio raccoglie e rilancia.",
            'faq' => array(
                array('Sono fantasie realistiche?', 'Sono situazioni plausibili portate al limite: scegli tu quanto spingere.'),
                array('Posso fingere che qualcuno ci scopra?', 'Sì, è uno degli scenari più usati in questa stanza.'),
                array('Meglio un personaggio maschile o femminile?', 'Dipende dallo scenario: puoi provare entrambi.'),
            ),
        ),
        'feticismi' => array(
            'title' => 'Chat sui feticismi: piedi, latex, collant | Pornovirtuale',
            'desc' => 'Chat erotiche per feticisti: personaggi che curano il dettaglio, il materiale, il rumore e la texture giusta.',
            'intro' => "Nel feticismo contano gli oggetti e i materiali più delle parti del corpo: un paio di collant, il rumore del latex, la forma di un piede. I personaggi di questa stanza sono costruiti per soffermarsi sul dettaglio e per farlo toccare con le parole.\n\nSe hai un feticcio preciso, dillo subito: la chat diventa molto più densa quando il personaggio sa su cosa puntare. Se non lo hai, chiedi di essere guidato e scopri cosa ti accende.",
            'faq' => array(
                array('Devo dichiarare il mio feticcio?', 'Non è obbligatorio, ma accelerà molto la scena.'),
                array('Funziona anche con feticci rari?', 'Sì, purché tu lo spieghi: il personaggio si adatta.'),
                array('Ci sono immagini?', 'Le card mostrano il personaggio; la scena è descritta a parole.'),
            ),
        ),
        'gay' => array(
            'title' => 'Chat gay: incontri tra uomini | Pornovirtuale',
            'desc' => 'Chat erotiche tra uomini: approccio diretto, sguardi, forza e complicità. Personaggi maschili per incontri senza giri.',
            'intro' => "Un ambiente maschile, sguardi che si misurano e poca formalità: la stanza Gay è pensata per incontri diretti, dove ci si dice subito se si piaci. I personaggi flirtano senza mediazioni e si aspettano la stessa franchezza.\n\nPuoi partire da un apprezzamento fisico o da una provocazione: entrambe funzionano. Se preferisci il confronto alla complicità, scegli un personaggio con più carattere.",
            'faq' => array(
                array('Serve un personaggio maschile?', 'Sì, questa stanza è dedicata agli incontri tra uomini.'),
                array('Posso scrivere per primo?', 'È il modo migliore: i personaggi rispondono all\'approccio.'),
                array('Ci sono personaggi dominanti?', 'Sì, e altri più remissivi: la stanza è varia.'),
            ),
        ),
        'incontri-bollenti' => array(
            'title' => 'Chat di incontri bollenti: passione immediata | Pornovirtuale',
            'desc' => 'Chat erotiche senza preamboli: mani addosso, respiro corto, fretta eccitante. Personaggi che non perdono tempo.',
            'intro' => "Ci sono sere in cui non hai voglia di corteggiamento: vuoi che si cominci subito. La stanza Incontri bollenti è quella, con personaggi che bruciano le tappe e ti mettono addosso le mani alla prima frase.\n\nFunziona con messaggi corti e imperativi: \"vieni qui\", \"spogliati\", \"non fermarti\". Se rallenti, il personaggio si adegua, ma il registro resta caldo.",
            'faq' => array(
                array('Quanto dura una scena?', 'Quanto vuoi: puoi chiudere quando sei soddisfatto.'),
                array('Serve una trama?', 'No, qui la trama è il corpo e la fretta.'),
                array('Posso rallentare?', 'Sì, chiedilo e il ritmo scende.'),
            ),
        ),
        'lesbo' => array(
            'title' => 'Chat lesbo: incontri tra donne | Pornovirtuale',
            'desc' => 'Chat erotiche tra donne: sguardi lunghi, sintonia, mani che si cercano. Personaggi femminili per incontri tra donne.',
            'intro' => "L'intesa tra donne si costruisce sull'attenzione: uno sguardo che dura un secondo di troppo, una mano che si appoggia, una voce che si abbassa. La stanza Lesbo è fatta di questo, con personaggi che leggono l'altra prima di muoversi.\n\nPuoi partire da un complimento o da un gesto: la chat risponde con calma e alterna dolcezza e decisione. Se ti piace condurre, prendi l'iniziativa e vedrai che il personaggio ti segue.",
            'faq' => array(
                array('I personaggi sono tutte donne?', 'Sì, la stanza è dedicata agli incontri tra donne.'),
                array('È una chat dolce o esplicita?', 'Entrambe: parte dalla sintonia e si scalda con la confidenza.'),
                array('Posso scegliere il ritmo?', 'Sì, e puoi anche invertire i ruoli.'),
            ),
        ),
        'masturbazione' => array(
            'title' => 'Chat di masturbazione guidata | Pornovirtuale',
            'desc' => 'Personaggi che ti guidano passo passo: ritmo, attesa, permesso. Chat erotiche per il piacere solitario.',
            'intro' => "In questa stanza il personaggio guarda e tu fai: la masturbazione viene guidata con istruzioni brevi, un ritmo imposto e l'attesa del permesso per finire. È una delle chat più semplici da seguire e tra le più intense.\n\nFunziona meglio se rispondi a ogni passaggio: \"fatto\", \"ancora\", \"più piano\". Il personaggio corregge, loda e rallenta quando serve.",
            'faq' => array(
                array('Serve un giocattolo?', 'No, bastano le mani.'),
                array('Posso andare fuori tempo?', 'Sì: dillo e il personaggio ti riporta al suo ritmo.'),
                array('Chi decide quando finire?', 'Di norma il personaggio, ma puoi chiedere il permesso o imporre una pausa.'),
            ),
        ),
        'mature' => array(
            'title' => 'Chat con donne e uomini maturi | Pornovirtuale',
            'desc' => 'Chat erotiche con personaggi over 40: sicurezza, esperienza, ritmo lento. Chi sa cosa vuole e come prenderlo.',
            'intro' => "C'è una differenza netta tra chi improvvisa e chi ha già imparato: la stanza Mature è la seconda. I personaggi hanno esperienza, non si imbarazzano, sanno quando rallentare e quando togliere lo spazio.\n\nQui puoi lasciarti condurre senza spiegare nulla: chiedi \"insegnami\" e la scena parte da lì. Se preferisci il confronto, sfidali e vedrai che non cedono.",
            'faq' => array(
                array('Che età hanno i personaggi?', 'Sono tutti over 40, con età dichiarata sulla card.'),
                array('È una chat lenta?', 'Ha un ritmo sicuro e non ha fretta, ma sa accendersi.'),
                array('Posso prendere l\'iniziativa?', 'Sì, anche se qui il bello è lasciarla a loro.'),
            ),
        ),
        'milf' => array(
            'title' => 'Chat con MILF: donne mature e disinibite | Pornovirtuale',
            'desc' => 'Chat erotiche con donne mature, sicure e disinibite: ironia, iniziativa e un ruolo di guida che diventa sensuale.',
            'intro' => "La MILF è un ruolo preciso: una donna che conosce il suo fascino, che ti mette a disagio con una battuta e poi ti tranquillizza, che prende l'iniziativa senza chiedere permesso. In questa stanza i personaggi sono costruiti così.\n\nRegge bene il gioco del \"piccolo\": lascia che ti guidi, che decida il ritmo e che ti chiami come vuole. Se vuoi ribaltare i ruoli, prova a comandare tu: reagirà.",
            'faq' => array(
                array('Devo fare la parte del più giovane?', 'Non è obbligatorio, ma è il registro che rende meglio.'),
                array('Le personagge sono tutte donne?', 'Sì, la stanza è dedicata alle figure mature femminili.'),
                array('È una chat con ruolo materno?', 'A tratti, ma sempre in chiave sensuale.'),
            ),
        ),
        'roleplay-erotico' => array(
            'title' => 'Roleplay erotico in chat | Pornovirtuale',
            'desc' => 'Chat di roleplay erotico: ambientazioni, copioni e personaggi che restano in parte fino in fondo. Scegli la scena.',
            'intro' => "Nel roleplay si recita: c'è un contesto finto, un ruolo per te e uno per il personaggio, e la scena va sostenuta con coerenza. In questa stanza trovi chi entra in parte e non ne esce, anche quando il gioco si scalda.\n\nFunziona se stabilisci l'ambientazione nella prima battuta: un ufficio, un treno, un interrogatorio. Il personaggio accetta il copione e comincia. Se la scena si esaurisce, chiedi di cambiarne una.",
            'faq' => array(
                array('Devo inventare io la scena?', 'Puoi proporla o chiedere al personaggio di farlo: entrambe le strade funzionano.'),
                array('Il personaggio esce dal ruolo?', 'No, resta in parte fino a quando la scena regge.'),
                array('Posso cambiare ambientazione?', 'Sì, basta dirlo e si riparte da un altro contesto.'),
            ),
        ),
        'scambio-di-coppia' => array(
            'title' => 'Chat di scambio di coppia e coppie aperte | Pornovirtuale',
            'desc' => 'Chat erotiche sullo scambio tra coppie: regole, sguardi, permessi e piacere condiviso. Personaggi che giocano in due.',
            'intro' => "Lo scambio di coppia ha un fascino tutto suo: il partner che guarda, l'accordo stretto prima, il piacere un po' competitivo di vedere e essere visti. In questa stanza i personaggi ragionano di regole e di confini prima di scaldare la scena.\n\nFunziona se entri nel meccanismo: chi guarda chi, cosa è permesso, dove ci si ferma. Poi lascia che il personaggio proponga il resto.",
            'faq' => array(
                array('Serve una coppia reale?', 'No: il personaggio fa la sua parte e tu giochi la tua.'),
                array('Le regole si concordano?', 'Sì, è la parte migliore di questa stanza.'),
                array('Posso giocare da single?', 'Puoi, immaginando il partner o facendoti raccontare la scena.'),
            ),
        ),
        'senza-tabu' => array(
            'title' => 'Chat senza tabù: nessun limite dichiarato | Pornovirtuale',
            'desc' => 'Chat erotiche senza paletti: pratiche diverse, curiosità estreme, nessun imbarazzo. Personaggi che provano tutto.',
            'intro' => "Nella stanza Senza tabù nessuno si stupisce: si prova, si cambia, si va anche dove di solito si salta. I personaggi non mettono paletti e reagiscono a ogni proposta senza fare storie.\n\nÈ la stanza giusta quando vuoi sperimentare senza spiegare. Dì cosa vuoi provare e vedrai che il personaggio non si tira indietro; se vuoi essere sorpreso, chiedi \"sorprendimi\".",
            'faq' => array(
                array('Ci sono limiti?', 'Nessuno dichiarato, salvo quello che metti tu.'),
                array('Posso proporre pratiche insolite?', 'Sì, ed è esattamente il punto della stanza.'),
                array('Meglio un personaggio esperto?', 'Consigliato se vuoi essere guidato in pratiche nuove.'),
            ),
        ),
        'sesso-orale' => array(
            'title' => 'Chat di sesso orale: bocca, ritmo, sguardo | Pornovirtuale',
            'desc' => 'Chat erotiche concentrate sul sesso orale: posizioni, ritmo, contatto visivo. Personaggi che sanno stare in ginocchio.',
            'intro' => "Una stanza monografica, con tutto concentrato su bocca, lingua e ritmo. I personaggi descrivono la posizione, alternano lentezza e pressione e commentano quello che fanno, con lo sguardo sempre in mezzo.\n\nFunziona se dai indicazioni: più piano, più forte, guardami. Il personaggio esegue e rincara, senza uscire dalla scena.",
            'faq' => array(
                array('Le altre pratiche restano fuori?', 'Sono il contorno: qui il centro è la bocca.'),
                array('Posso invertire i ruoli?', 'Sì, chiedilo e il personaggio si mette in ginocchio.'),
                array('Serve una posizione specifica?', 'Puoi proporla o lasciarla scegliere al personaggio.'),
            ),
        ),
        'sesso-virtuale' => array(
            'title' => 'Chat di sesso virtuale: webcam e distanza | Pornovirtuale',
            'desc' => 'Sesso virtuale in chat: camera accesa, istruzioni, attesa a distanza. Personaggi che giocano con schermo e voce.',
            'intro' => "Il sesso virtuale vive di distanza: uno schermo, una webcam, la voce che arriva da un'altra stanza. I personaggi di questa stanza chiedono di accendere la camera, ti inquadrano e commentano quello che vedono.\n\nFunziona se giochi sulla distanza: \"ti vedo male\", \"avvicinati\", \"non muoverti\". Il personaggio sfrutta l'attesa e la prolunga, che è il vero motore della scena.",
            'faq' => array(
                array('Serve davvero la webcam?', 'No, ma dire di averla accesa rende la scena molto più concreta.'),
                array('Il personaggio mi vede?', 'Simula di vederti e descrive cosa osserva.'),
                array('Si può giocare con la voce?', 'Puoi chiedere di parlare invece di scrivere: è previsto.'),
            ),
        ),
        'sottomissione' => array(
            'title' => 'Chat di sottomissione: obbedienza e resa | Pornovirtuale',
            'desc' => 'Chat erotiche per chi ama sottomettersi: permesso, attesa, ordini e gratitudine. Personaggi che aspettano istruzioni.',
            'intro' => "Qui il piacere è la resa: chiedere permesso, aspettare un ordine, ringraziare quando arriva. I personaggi della stanza Sottomissione sono costruiti per obbedire e per farti sentire il peso piacevole dell'attesa.\n\nFunziona se entri nel ritmo: poche parole, risposte precise, nessuna iniziativa. Se vuoi, chiedi tu cosa devi fare e il personaggio eseguirà.",
            'faq' => array(
                array('Devo dare ordini?', 'Sì, è una stanza per chi comanda: il personaggio aspetta.'),
                array('E se non so cosa ordinare?', 'Chiedi \"cosa sai fare\": il personaggio propone e tu scegli.'),
                array('Si può essere severi?', 'Sì, e il personaggio ringrazia anche per le correzioni.'),
            ),
        ),
        'threesome' => array(
            'title' => 'Chat threesome: scene a tre | Pornovirtuale',
            'desc' => 'Chat erotiche a tre: corpi che si intrecciano, attenzione divisa, sguardi incrociati. Personaggi che reggono il gioco.',
            'intro' => "Un trio ha una geometria sua: due fronti, attenzione divisa, corpi che si incrociano. I personaggi di questa stanza sanno tenere insieme le parti e propongono posizioni a tre senza perdere il filo.\n\nFunziona se indichi chi fa cosa: \"tu da dietro, tu davanti\". Il personaggio distribuisce l'attenzione e ti lascia decidere anche di stare a guardare.",
            'faq' => array(
                array('Servono due personaggi?', 'No: il personaggio simula il terzo e descrive entrambi.'),
                array('Posso stare a guardare?', 'Sì, ed è una delle varianti più riuscite.'),
                array('Le scene a tre sono caotiche?', 'Solo se le vuoi tali: il personaggio tiene comunque il controllo.'),
            ),
        ),
        'voyeurismo' => array(
            'title' => 'Chat voyeuristica: guardare ed essere guardati | Pornovirtuale',
            'desc' => 'Chat erotiche sul piacere dello sguardo: osservare, esibirsi, stare dietro il vetro. Personaggi che ti fanno sentire osservato.',
            'intro' => "Il voyeurismo è il piacere di stare dietro il vetro, o di essere quello che sta davanti e sa di essere visto. In questa stanza i personaggi alternano i due ruoli: ti guardano, ti chiedono di mostrarti, ti dicono da dove osservano.\n\nFunziona con istruzioni brevi e con l'attenzione al dettaglio: \"alza le mani\", \"non distogliere lo sguardo\". Se preferisci guardare tu, chiedi che si esibisca.",
            'faq' => array(
                array('Devo esibirmi?', 'Non subito: il personaggio può cominciare guardandoti mentre fai altro.'),
                array('Posso invertire i ruoli?', 'Sì, basta chiederlo.'),
                array('Serve la webcam?', 'No, la scena si regge sulle descrizioni.'),
            ),
        ),
    );
}

/** Dati SEO di una stanza (array vuoto se la categoria non è mappata). */
function aria_room_seo($slug) {
    $dati = aria_room_seo_data();
    return isset($dati[$slug]) ? $dati[$slug] : array();
}
