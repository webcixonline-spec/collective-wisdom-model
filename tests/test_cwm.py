"""Test di CWM 1.2 (solo libreria standard): python -m unittest discover -s tests -v"""
from __future__ import annotations

import contextlib
import copy
import datetime
import io
import json
import math
import random
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from cwm import analysis, audit, benchmark, costi, education as edu, elicitazione, ema_bridge as eb, evidence, lake, robust, stats, voi, weights  # noqa: E402

PAC = analysis.carica_pacchetto()
RIS = analysis.esegui(PAC)


def pac_con_partecipanti_reali() -> dict:
    """Gli stessi giudizi dell'esempio, documentati come se fossero stati raccolti da persone reali."""
    pac = copy.deepcopy(PAC)
    doc = pac["partecipanti"]
    doc.update({"natura": "reale", "facilitatore": "Facilitatore di prova", "protocollo": "docs/elicitazione.md v1"})
    for p in doc["partecipanti"]:
        p.update({"data": "2026-10-01", "consenso": True})
    return pac


class TestStatistica(unittest.TestCase):
    def test_lhs_un_punto_per_strato(self):
        pts = stats.lhs({"a": (0, 1), "b": (10, 20)}, 50, 1)
        for k, (lo, hi) in {"a": (0, 1), "b": (10, 20)}.items():
            strati = sorted(int((p[k] - lo) / (hi - lo) * 50) for p in pts)
            self.assertEqual(strati, list(range(50)))

    def test_regressione_cubica_esatta(self):
        x = [i / 10 for i in range(40)]
        y = [2 - x_ + 0.5 * x_ ** 3 for x_ in x]
        for a, b in zip(stats.polyfit_predict(x, y, 3), y):
            self.assertAlmostEqual(a, b, places=6)

    def test_kendall(self):
        self.assertAlmostEqual(stats.kendall_tau([1, 2, 3], [1, 2, 3]), 1.0)
        self.assertAlmostEqual(stats.kendall_tau([1, 2, 3], [3, 2, 1]), -1.0)


class TestFase08(unittest.TestCase):
    def test_modello_non_lineare_scelta_interna(self):
        """Con la 0.7 lineare vinceva sempre un estremo; ora politiche interne vincono in alcuni scenari."""
        m = RIS["metriche_train"]
        self.assertGreater(m["35/25"]["vittorie_uniche"] + m["40/20"]["vittorie_uniche"], 0)

    def test_estrapolazione_davvero_fuori(self):
        for s in edu.scenari_estrapolazione(40, 3):
            self.assertTrue(any(not (edu.INTERVALLI_TRAIN[k][0] <= v <= edu.INTERVALLI_TRAIN[k][1]) for k, v in s.items()))

    def test_holdout_puo_fallire(self):
        esiti = {v["holdout"]: v["esito"] for v in RIS["validazione"]}
        self.assertIn("NON_SUPERATO", esiti.values(), "almeno un holdout deve poter fallire con questo piano")
        for v in RIS["validazione"]:
            self.assertAlmostEqual(v["scarto"], v["rimpianto_massimo_scelta_train"] - v["rimpianto_massimo_ottimale"])
            self.assertGreaterEqual(v["scarto"], -1e-12)

    def test_nessuna_riga_duplicata(self):
        politiche = [c["politica"] for c in RIS["confronto_strategie"]]
        self.assertEqual(len(politiche), len(set(politiche)))

    def test_cancello_graduato(self):
        self.assertEqual(RIS["verdetti_per_obiettivo"]["raccomandazione_nazionale"], "ABSTAIN")
        # con le UCS PNRR e il CCNL i costi arrivano a prova "bassa": il pilota passa senza riserve,
        # il programma locale resta in astensione finché mancano preventivi degli istituti
        self.assertEqual(RIS["verdetti_per_obiettivo"]["pilota_valutato"], "PASS")
        self.assertEqual(RIS["verdetti_per_obiettivo"]["programma_locale"], "ABSTAIN")

    def test_livello_grade(self):
        self.assertEqual(evidence.livello_fonte({"disegno": "rct", "declassamenti": {"indirettezza": 1}}), 3)
        self.assertEqual(evidence.livello_fonte({"disegno": "osservazionale", "declassamenti": {"imprecisione": 2}}), 1)
        self.assertEqual(evidence.livello_fonte({"disegno": "assunzione"}), 0)
        self.assertIsNone(evidence.livello_fonte({"disegno": "metodologia"}))

    def test_nuove_prove_cambiano_il_verdetto(self):
        reg = copy.deepcopy(PAC["registro"])
        reg["fonti"].append({"id": "preventivi", "disegno": "dato_amministrativo_verificato", "declassamenti": {"indirettezza": 1},
                             "sostiene_parametri": ["costo_svantaggiati", "costo_altri"]})
        reg["fonti"].append({"id": "rct_gruppi", "disegno": "rct", "declassamenti": {"imprecisione": 1, "indirettezza": 1},
                             "sostiene_parametri": ["moltiplicatore"]})
        par = sorted(edu.INTERVALLI_TRAIN)
        self.assertEqual(evidence.cancello(reg, PAC["requisiti"], "programma_locale", par)["verdetto"], "PASS")
        self.assertEqual(evidence.cancello(reg, PAC["requisiti"], "pilota_valutato", par)["verdetto"], "PASS")


class TestFase09(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ris = eb.carica_risultati(str(benchmark.CARTELLA / "lake_ema_results.tar.gz"))
        cls.rif = json.loads((benchmark.CARTELLA / "lake_ema_reference.json").read_text(encoding="utf-8"))

    def test_struttura_file_ema(self):
        self.assertEqual(len(self.ris.esperimenti), 1200)
        self.assertEqual(self.ris.leve(), ["base", "ampiezza"])
        self.assertEqual(self.ris.incertezze(), ["b", "q", "mean", "stdev", "delta"])

    def test_stessi_numeri_di_ema(self):
        an = eb.analizza(self.ris, self.rif["direzioni"], self.rif["pesi"], {k: tuple(v) for k, v in self.rif["soglie"].items()})
        self.assertLess(benchmark._max_diff(self.rif["per_esito"], an["per_esito"]), 1e-12)
        self.assertLess(benchmark._max_diff(self.rif["composita"], an["composita"]), 1e-12)
        self.assertLess(benchmark._max_diff(self.rif["quota_soddisfacente"], an["quota_soddisfacente"]), 1e-12)
        self.assertEqual(an["scelta_minimax"], self.rif["scelta_minimax"])

    def test_modello_lake_esiti_deterministici(self):
        for i in (0, 333, 777, 1199):
            e = self.ris.esperimenti[i]
            out = lake.lake_problem(b=e["b"], q=e["q"], mean=e["mean"], stdev=e["stdev"], delta=e["delta"], n_samples=5,
                                    decisions=lake.decisioni_alternate(e["base"], e["ampiezza"]), backend="python")
            self.assertAlmostEqual(out[1], self.ris.esiti["utility"][i], places=12)
            self.assertEqual(out[2], self.ris.esiti["inertia"][i])

    def test_modello_lake_numpy_identico(self):
        try:
            import numpy  # noqa: F401
        except ImportError:
            self.skipTest("numpy non installato")
        f = benchmark.fedelta_modello(self.ris, 12, "numpy")
        self.assertLess(max(f["differenza_massima_assoluta"].values()), 1e-12)  # arrotondamenti diversi tra CPU e libm


class TestFase10(unittest.TestCase):
    def test_disuguaglianze_voi(self):
        v = RIS["valore_informazione"]
        for p, d in v["per_parametro"].items():
            self.assertGreaterEqual(d["evppi"], 0)
            self.assertLessEqual(d["evppi"], v["evpi"] + 1e-9, p)
            self.assertGreaterEqual(d["voi_r"], 0)
            self.assertLessEqual(d["voi_r"], d["rimpianto_massimo_ora"] + 1e-12)

    def test_evppi_parametro_irrilevante(self):
        rng = random.Random(0)
        x = [rng.random() for _ in range(500)]
        u = {"a": [xi for xi in x], "b": [1 - xi for xi in x]}
        rumore = [rng.random() for _ in range(500)]
        self.assertGreater(voi.evppi(u, x), 0.2)
        self.assertLess(voi.evppi(u, rumore), 0.02)

    def test_evsi_limitato_e_crescente(self):
        for st in RIS["valore_informazione"]["studi"]:
            vals = [c["evsi"] for c in st["curva"]]
            self.assertEqual(vals, sorted(vals))
            for c in st["curva"]:
                self.assertLessEqual(c["evsi"], c["evppi_tetto"] + 1e-12)

    def test_isotonica(self):
        self.assertEqual(voi.isotonica([1, 3, 2, 4]), [1, 2.5, 2.5, 4])


class TestFase11(unittest.TestCase):
    C = ("a", "b", "c")

    def _giudizi(self, w):
        return [{"a": self.C[i], "b": self.C[j], "valore": w[i] / w[j]} for i in range(3) for j in range(i + 1, 3)]

    def test_ahp_coerente_recupera_i_pesi(self):
        w = [0.5, 0.3, 0.2]
        agg = weights.aggrega(self.C, [{"id": "x", "giudizi": self._giudizi(w)}])
        for c, v in zip(self.C, w):
            self.assertAlmostEqual(agg["pesi_gruppo"][c], v, places=9)
        self.assertLess(agg["cr_gruppo"], 1e-9)

    def test_incoerenti_esclusi(self):
        circolare = [{"a": "a", "b": "b", "valore": 9}, {"a": "b", "b": "c", "valore": 9}, {"a": "a", "b": "c", "valore": 1 / 9}]
        agg = weights.aggrega(self.C, [{"id": "ok", "giudizi": self._giudizi([.4, .4, .2])}, {"id": "no", "giudizi": circolare}])
        self.assertEqual([e["id"] for e in agg["partecipanti_esclusi"]], ["no"])

    def test_vincoli_non_compensabili(self):
        self.assertNotIn("60/0", RIS["vincoli"]["ammesse"])
        self.assertNotIn("20/40", RIS["vincoli"]["ammesse"])
        for pesi in ({c: (1.0 if c == "accesso" else 0.0) for c in edu.CRITERI},):
            r = analysis.esegui(PAC, pesi=pesi, con_studi=False, con_stabilita=False)
            self.assertIn(r["scelta_minimax"], r["vincoli"]["ammesse"])

    def test_smaa_e_raggio(self):
        st = RIS["stabilita_pesi"]
        self.assertAlmostEqual(sum(st["smaa_attorno_ai_pesi"].values()), 1.0)
        self.assertGreater(st["raggio"]["distanza"], 0)
        self.assertNotEqual(st["raggio"]["nuova_scelta"], st["raggio"]["scelta_attuale"])


class TestFase12(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.reg = audit.Registro(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_catena_rileva_manomissioni(self):
        self.reg.aggiungi("PROVA", {"x": 1})
        self.reg.aggiungi("PROVA", {"x": 2})
        self.assertTrue(self.reg.verifica_catena()["integro"])
        righe = self.reg.file.read_text(encoding="utf-8").splitlines()
        righe[0] = righe[0].replace('"x": 1', '"x": 9')
        self.reg.file.write_text("\n".join(righe) + "\n", encoding="utf-8")
        self.assertFalse(self.reg.verifica_catena()["integro"])

    def test_deviazioni_dalla_preregistrazione(self):
        self.reg.preregistra(PAC)
        self.assertEqual(self.reg.deviazioni(PAC)["deviazioni"], [])
        pac2 = copy.deepcopy(PAC)
        pac2["analisi"]["validazione"]["tolleranza_trasferimento"] = 0.5
        self.assertTrue(any("analisi" in d for d in self.reg.deviazioni(pac2)["deviazioni"]))
        pac3 = copy.deepcopy(PAC)
        pac3["partecipanti"]["partecipanti"] = pac3["partecipanti"]["partecipanti"][:2]
        self.assertFalse(self.reg.controlli_uso(pac3, RIS)["consentito"], "cambiare i pesi dopo la preregistrazione blocca l'uso")

    def test_raccomandazione_nazionale_bloccata(self):
        reale = pac_con_partecipanti_reali()
        self.assertFalse(self.reg.controlli_uso(reale, RIS, "raccomandazione_nazionale")["consentito"])
        self.assertTrue(self.reg.controlli_uso(reale, RIS, "pilota_valutato")["consentito"])

    def test_preferenze_sintetiche_non_reggono_una_raccomandazione(self):
        c = self.reg.controlli_uso(PAC, RIS, "pilota_valutato")
        self.assertFalse(c["consentito"])
        self.assertTrue(any("sintetica" in b for b in c["blocchi"]))
        self.assertTrue(self.reg.controlli_uso(PAC, RIS)["consentito"], "in analisi esplorativa è solo un avviso")

    def test_riproducibilita(self):
        r2 = analysis.esegui(json.loads(json.dumps(audit.pulisci(PAC))))
        self.assertEqual(audit.hash_esiti(RIS), audit.hash_esiti(r2))

    def test_interfaccia_web(self):
        from cwm.server import crea_server
        srv = crea_server(0, str(analysis.CONFIG), self.tmp.name)
        th = threading.Thread(target=srv.serve_forever, daemon=True)
        th.start()
        try:
            url = f"http://127.0.0.1:{srv.server_address[1]}"
            base = json.loads(urllib.request.urlopen(url + "/api/base", timeout=30).read())
            self.assertEqual(base["criteri"], list(edu.CRITERI))
            req = urllib.request.Request(url + "/api/analizza", data=json.dumps({"stabilita": False}).encode(),
                                         headers={"Content-Type": "application/json"})
            r = json.loads(urllib.request.urlopen(req, timeout=60).read())
            self.assertEqual(r["scelta_minimax"], RIS["scelta_minimax"])
            self.assertIn("<title>CWM 1.2</title>", urllib.request.urlopen(url + "/", timeout=30).read().decode())
        finally:
            srv.shutdown()
            srv.server_close()


class TestGovernance(unittest.TestCase):
    """Deviazioni dal piano preregistrato: blocco per sezione, non per sottostringa."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.reg = audit.Registro(self.tmp.name)
        self.reg.preregistra(PAC)

    def tearDown(self):
        self.tmp.cleanup()

    def test_soglie_di_prova_abbassate_bloccano(self):
        pac = copy.deepcopy(PAC)
        pac["requisiti"]["obiettivi"]["raccomandazione_nazionale"]["parametri"]["effetto"]["minimo"] = 1
        self.assertFalse(self.reg.controlli_uso(pac, RIS)["consentito"])

    def test_vincoli_allentati_bloccano(self):
        pac = copy.deepcopy(PAC)
        pac["vincoli"]["vincoli"][0]["valore"] = 0
        self.assertFalse(self.reg.controlli_uso(pac, RIS)["consentito"])

    def test_tolleranza_holdout_cambiata_blocca(self):
        pac = copy.deepcopy(PAC)
        pac["analisi"]["validazione"]["tolleranza_trasferimento"] = 0.5
        self.assertFalse(self.reg.controlli_uso(pac, RIS)["consentito"])

    def test_semi_cambiati_solo_avviso(self):
        pac = copy.deepcopy(PAC)
        pac["analisi"]["semi"]["train"] += 1
        c = self.reg.controlli_uso(pac, RIS)
        self.assertTrue(c["consentito"])
        self.assertTrue(any("semi" in a for a in c["avvisi"]))

    def test_pesi_manuali_dopo_preregistrazione_bloccano(self):
        r = analysis.esegui(PAC, pesi={c: 1.0 for c in edu.CRITERI}, con_studi=False, con_stabilita=False)
        self.assertFalse(self.reg.controlli_uso(PAC, r)["consentito"])
        with tempfile.TemporaryDirectory() as libero:
            self.assertTrue(audit.Registro(libero).controlli_uso(PAC, r)["consentito"], "senza preregistrazione è solo un avviso")


class TestVerifica(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_analisi_da_interfaccia_riproducibile(self):
        from cwm.server import Applicazione
        app = Applicazione(str(analysis.CONFIG), self.tmp.name)
        pesi = {c: float(i + 1) for i, c in enumerate(edu.CRITERI)}
        app.analizza({"pesi": pesi, "obiettivo": "pilota_valutato", "stabilita": True, "registra": True})
        voce = app.registro.ultima("ANALISI")["contenuto"]
        rifatta = analysis.riesegui(json.loads(json.dumps(voce["input"])), json.loads(json.dumps(voce["opzioni"])))
        self.assertEqual(audit.hash_esiti(rifatta), voce["hash_esiti"])

    def test_voci_nel_formato_precedente(self):
        r = analysis.riesegui(PAC, {"obiettivo": None, "rapido": False})
        self.assertEqual(audit.hash_esiti(r), audit.hash_esiti(RIS))

    def test_registro_vuoto_non_e_un_successo(self):
        from cwm.__main__ import main
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--audit", self.tmp.name, "verifica"]), 1)


class TestValidazioneInput(unittest.TestCase):
    def test_pesi_non_validi(self):
        buoni = {c: 1.0 for c in edu.CRITERI}
        casi = [dict(buoni, equita=-1.0), dict(buoni, equita=float("nan")), dict(buoni, equita=float("inf")),
                dict(buoni, equita=True), dict(buoni, equita="1"), {c: 0.0 for c in edu.CRITERI},
                {c: 1.0 for c in edu.CRITERI[:-1]}, dict(buoni, extra=1.0), [1, 2, 3]]
        for pesi in casi:
            with self.subTest(pesi=pesi), self.assertRaises(ValueError):
                analysis.esegui(PAC, pesi=pesi, con_studi=False, con_stabilita=False)

    def test_operatore_di_vincolo_sconosciuto(self):
        pol = edu.politiche()
        with self.assertRaises(ValueError):
            weights.applica_vincoli(pol, [{"id": "X", "attributo": "svantaggiati", "operatore": ">", "valore": 30}])
        with self.assertRaises(ValueError):
            weights.applica_vincoli(pol, [{"id": "X", "attributo": "svantagiati", "operatore": ">=", "valore": 30}])

    def test_cancello_vuoto_o_malformato(self):
        par = sorted(edu.INTERVALLI_TRAIN)
        for parametri in ({}, {"efetto": {"minimo": 2}}, {"effetto": {"minimo": 3, "desiderato": 2}},
                          {"effetto": {"minimo": 5}}, {"effetto": {"minimo": "2"}}):
            req = {"obiettivi": {"x": {"parametri": parametri}}}
            with self.subTest(parametri=parametri), self.assertRaises(ValueError):
                evidence.cancello(PAC["registro"], req, "x", par)

    def test_fonte_malformata(self):
        with self.assertRaises(ValueError):
            evidence.livello_fonte({"disegno": "RCT"})
        with self.assertRaises(ValueError):
            evidence.livello_fonte({"disegno": "osservazionale", "declassamenti": {"imprecisione": -2}})
        with self.assertRaises(ValueError):
            evidence.livello_fonte({"disegno": "rct", "declassamenti": {"indiretezza": 1}})


class TestAHP(unittest.TestCase):
    C = ("a", "b", "c")
    COMPLETI = [{"a": "a", "b": "b", "valore": 2}, {"a": "b", "b": "c", "valore": 2}, {"a": "a", "b": "c", "valore": 4}]

    def test_piu_di_dieci_criteri_non_passano_per_coerenti(self):
        n = 11
        m = [[1.0 if i == j else (9.0 if (j - i) % n <= n // 2 else 1 / 9) for j in range(n)] for i in range(n)]
        with self.assertRaises(ValueError):
            weights.coerenza(m)

    def test_giudizio_con_se_stesso_non_copre_un_mancante(self):
        g = [self.COMPLETI[0], self.COMPLETI[1], {"a": "a", "b": "a", "valore": 3}]
        with self.assertRaises(ValueError):
            weights.matrice_da_giudizi(self.C, g)

    def test_confronto_ripetuto(self):
        with self.assertRaises(ValueError):
            weights.matrice_da_giudizi(self.C, self.COMPLETI + [{"a": "b", "b": "a", "valore": 3}])

    def test_criterio_sconosciuto(self):
        with self.assertRaises(ValueError):
            weights.matrice_da_giudizi(self.C, self.COMPLETI[:2] + [{"a": "a", "b": "z", "valore": 4}])

    def test_partecipanti_ripetuti(self):
        p = {"id": "x", "giudizi": self.COMPLETI}
        with self.assertRaises(ValueError):
            weights.aggrega(self.C, [p, dict(p)])


class TestServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from cwm.server import crea_server
        cls.tmp = tempfile.TemporaryDirectory()
        cls.srv = crea_server(0, str(analysis.CONFIG), cls.tmp.name)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.srv.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.tmp.cleanup()

    def _richiesta(self, percorso, corpo=None, intestazioni=None):
        dati = None if corpo is None else (corpo if isinstance(corpo, bytes) else json.dumps(corpo).encode())
        h = {"Content-Type": "application/json"} if dati is not None else {}
        h.update(intestazioni or {})
        req = urllib.request.Request(self.url + percorso, data=dati, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_origine_esterna_rifiutata(self):
        stato, _ = self._richiesta("/api/analizza", {"registra": True}, {"Origin": "https://sito-malevolo.example"})
        self.assertEqual(stato, 403)
        self.assertEqual(audit.Registro(self.tmp.name).voci(), [], "nessuna voce scritta da un'altra origine")

    def test_dns_rebinding_rifiutato(self):
        self.assertEqual(self._richiesta("/api/base", intestazioni={"Host": "attaccante.example:8765"})[0], 403)

    def test_content_type_non_json_rifiutato(self):
        stato, _ = self._richiesta("/api/analizza", b'{"registra": true}', {"Content-Type": "text/plain"})
        self.assertEqual(stato, 415)

    def test_corpo_troppo_grande(self):
        from cwm.server import MAX_CORPO
        self.assertEqual(self._richiesta("/api/analizza", b" " * (MAX_CORPO + 1))[0], 413)

    def test_input_non_valido_e_400_chiaro(self):
        stato, r = self._richiesta("/api/analizza", {"pesi": {c: 0 for c in edu.CRITERI}})
        self.assertEqual(stato, 400)
        self.assertIn("somma dei pesi", r["errore"])
        self.assertEqual(self._richiesta("/api/analizza", {"obiettivo": "inesistente"})[0], 400)
        self.assertEqual(self._richiesta("/api/analizza", {"stabilita": "sì"})[0], 400)

    def test_stessa_origine_accettata(self):
        stato, r = self._richiesta("/api/analizza", {"stabilita": False}, {"Origin": self.url})
        self.assertEqual(stato, 200)
        self.assertEqual(r["scelta_minimax"], RIS["scelta_minimax"])


class TestJSONRigoroso(unittest.TestCase):
    def test_canonico_rifiuta_valori_ambigui(self):
        for obj in ({"x": float("nan")}, {"x": float("inf")}, {1: "a"}, {"x": {1, 2}}):
            with self.subTest(obj=obj), self.assertRaises(ValueError):
                audit.canonico(obj)
        self.assertEqual(audit.canonico({"b": 1, "a": [1.5, None, "è"]}), '{"a":[1.5,null,"è"],"b":1}'.encode())

    def test_pulisci_non_nasconde_nan(self):
        self.assertEqual(audit.pulisci({"x": float("inf"), "y": (1, 2)}), {"x": None, "y": [1, 2]})
        with self.assertRaises(ValueError):
            audit.pulisci({"a": [1.0, float("nan")]})
        with self.assertRaises(ValueError):
            audit.pulisci({1: "a", "1": "b"})

    def test_hash_esiti_distingue_inf_da_null(self):
        self.assertNotEqual(audit.hash_esiti({"x": float("inf")}), audit.hash_esiti({"x": None}))
        self.assertEqual(audit.hash_esiti({"x": float("inf")}, 1), audit.hash_esiti({"x": None}, 1), "formato 1: storico")
        with self.assertRaises(ValueError):
            audit.hash_esiti({"x": float("nan")})

    def test_lettura_rifiuta_chiavi_ripetute_e_nan(self):
        for testo in ('{"a": 1, "a": 2}', '{"a": NaN}', '{"a": Infinity}', '{"a": '):
            with self.subTest(testo=testo), self.assertRaises(ValueError):
                audit.carica_json_rigoroso(testo)


def _aggiungi_da_processo(cartella: str, quante: int) -> None:
    reg = audit.Registro(cartella)
    for i in range(quante):
        reg.aggiungi("PROVA", {"i": i})


class TestRegistroRobusto(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.reg = audit.Registro(self.tmp.name)
        for i in range(3):
            self.reg.aggiungi("PROVA", {"i": i})

    def tearDown(self):
        self.tmp.cleanup()

    def _righe(self):
        return self.reg.file.read_text(encoding="utf-8").splitlines()

    def _scrivi(self, testo: str):
        self.reg.file.write_text(testo, encoding="utf-8")

    def test_riga_incompleta_compromette_e_blocca_le_scritture(self):
        self._scrivi("\n".join(self._righe()) + "\n" + self._righe()[0][:40])
        cat = self.reg.verifica_catena()
        self.assertFalse(cat["integro"])
        self.assertIn("incompleta", cat["errori"][0])
        with self.assertRaises(audit.RegistroCorrotto):
            self.reg.aggiungi("PROVA", {})

    def test_chiave_ripetuta_non_vince_in_silenzio(self):
        righe = self._righe()
        righe[1] = righe[1][:-1] + ', "tipo": "ALTRO"}'
        self._scrivi("\n".join(righe) + "\n")
        cat = self.reg.verifica_catena()
        self.assertFalse(cat["integro"])
        self.assertIn("riga 2", cat["errori"][0])

    def test_nan_nel_file_compromette(self):
        righe = self._righe()
        righe[0] = righe[0].replace('"i": 0', '"i": NaN')
        self._scrivi("\n".join(righe) + "\n")
        self.assertFalse(self.reg.verifica_catena()["integro"])

    def test_nan_nel_contenuto_rifiutato_prima_di_scrivere(self):
        with self.assertRaises(ValueError):
            self.reg.aggiungi("PROVA", {"x": float("nan")})
        self.assertEqual(len(self._righe()), 3)

    def test_ogni_voce_va_su_disco(self):
        from unittest import mock
        with mock.patch("cwm.audit.os.fsync", wraps=audit.os.fsync) as fsync:
            self.reg.aggiungi("PROVA", {})
        fsync.assert_called_once()

    def test_scrittori_concorrenti_nello_stesso_processo(self):
        fili = [threading.Thread(target=_aggiungi_da_processo, args=(self.tmp.name, 10)) for _ in range(4)]
        for f in fili:
            f.start()
        for f in fili:
            f.join()
        cat = self.reg.verifica_catena()
        self.assertTrue(cat["integro"], cat["errori"])
        self.assertEqual(cat["voci"], 43)

    def test_scrittori_concorrenti_in_processi_diversi(self):
        import multiprocessing
        ctx = multiprocessing.get_context("spawn")
        proc = [ctx.Process(target=_aggiungi_da_processo, args=(self.tmp.name, 8)) for _ in range(3)]
        for p in proc:
            p.start()
        for p in proc:
            p.join(120)
            self.assertEqual(p.exitcode, 0)
        cat = self.reg.verifica_catena()
        self.assertTrue(cat["integro"], cat["errori"])
        self.assertEqual(cat["voci"], 27)


class TestCheckpoint(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.reg = audit.Registro(self.tmp.name)
        for i in range(3):
            self.reg.aggiungi("PROVA", {"i": i})
        self.cp = self.reg.checkpoint()

    def tearDown(self):
        self.tmp.cleanup()

    def test_storia_estesa_dopo_il_checkpoint(self):
        self.reg.aggiungi("PROVA", {"i": 3})
        cat = self.reg.verifica_catena(self.cp)
        self.assertTrue(cat["integro"])
        self.assertEqual(cat["checkpoint"], {"voci_attestate": 3, "voci_successive": 1})

    def test_troncamento_rilevato(self):
        righe = self.reg.file.read_text(encoding="utf-8").splitlines()
        self.reg.file.write_text("\n".join(righe[:2]) + "\n", encoding="utf-8")
        self.assertTrue(self.reg.verifica_catena()["integro"], "senza checkpoint il troncamento non si vede")
        cat = self.reg.verifica_catena(self.cp)
        self.assertFalse(cat["integro"])
        self.assertIn("troncato", cat["errori"][0])

    def test_riscrittura_con_la_chiave_rilevata(self):
        self.reg.file.unlink()  # chi ha la chiave ricostruisce una catena diversa, firmata e coerente
        for i in (0, 1, 99):
            self.reg.aggiungi("PROVA", {"i": i})
        self.assertTrue(self.reg.verifica_catena()["integro"])
        cat = self.reg.verifica_catena(self.cp)
        self.assertFalse(cat["integro"])
        self.assertIn("riscritta", cat["errori"][0])

    def test_checkpoint_malformato_o_su_registro_vuoto(self):
        for cp in ({}, dict(self.cp, voci=0), dict(self.cp, voci="3"), dict(self.cp, ultimo_hash="abc"), dict(self.cp, formato="x")):
            with self.subTest(cp=cp), self.assertRaises(ValueError):
                self.reg.verifica_catena(cp)
        with tempfile.TemporaryDirectory() as vuota, self.assertRaises(ValueError):
            audit.Registro(vuota).checkpoint()

    def test_riga_di_comando(self):
        from cwm.__main__ import main
        out = Path(self.tmp.name) / "altrove" / "cp.json"
        silenzio = contextlib.redirect_stdout(io.StringIO())
        with silenzio, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["--audit", self.tmp.name, "checkpoint", "--out", str(out)]), 0)
            self.assertEqual(main(["--audit", self.tmp.name, "checkpoint", "--out", str(out)]), 1, "mai sovrascrivere")
            self.assertEqual(main(["--audit", self.tmp.name, "verifica", "--checkpoint", str(out)]), 0)
            righe = self.reg.file.read_text(encoding="utf-8").splitlines()
            self.reg.file.write_text(righe[0] + "\n", encoding="utf-8")
            self.assertEqual(main(["--audit", self.tmp.name, "verifica", "--checkpoint", str(out)]), 1)


class TestCompatibilitaRegistro(unittest.TestCase):
    def test_voce_analisi_precedente_resta_verificabile(self):
        """Le voci 1.2.0 non hanno 'formato_hash_esiti' e hanno l'hash calcolato con inf -> null."""
        from cwm.__main__ import main
        with tempfile.TemporaryDirectory() as tmp:
            audit.Registro(tmp).aggiungi("ANALISI", {"input": PAC, "opzioni": {"obiettivo": None, "rapido": False},
                                                     "hash_esiti": audit.hash_esiti(RIS, 1)})
            with contextlib.redirect_stdout(io.StringIO()) as uscita:
                self.assertEqual(main(["--audit", tmp, "verifica"]), 0)
            self.assertIn("RIPRODOTTA", uscita.getvalue())


def _fonte(id_, disegno, decl, stime):
    return {"id": id_, "disegno": disegno, "declassamenti": decl, "sostiene_parametri": sorted(stime),
            "stime": {p: {"intervallo": list(iv), "derivazione": "prova"} for p, iv in stime.items()}}


class TestIntervalliDalleFonti(unittest.TestCase):
    IPOTESI = {"effetto": (0.1, 0.3), "saturazione": (0.0, 0.6)}

    def test_inviluppo_delle_fonti_migliori(self):
        reg = {"fonti": [_fonte("a", "rct", {"indirettezza": 1}, {"effetto": (0.20, 0.26)}),             # livello 3
                         _fonte("b", "meta_analisi_rct", {"indirettezza": 2}, {"effetto": (0.29, 0.37)}),  # livello 2
                         _fonte("c", "parere_esperti", {}, {"effetto": (0.05, 0.9)})]}                     # livello 1: escluso
        iv = evidence.intervalli_da_registro(reg, self.IPOTESI)
        self.assertEqual(iv["effetto"]["intervallo"], [0.20, 0.37])
        self.assertEqual(iv["effetto"]["fonti"], ["a", "b"])
        self.assertEqual(iv["effetto"]["fonti_escluse"], ["c"])
        self.assertEqual(iv["saturazione"], {"intervallo": [0.0, 0.6], "origine": "ipotesi", "fonti": [], "fonti_escluse": []})

    def test_stime_non_valide_rifiutate(self):
        casi = [_fonte("x", "rct", {}, {"effetto": (0.3, 0.2)}),
                _fonte("x", "rct", {}, {"sconosciuto": (0, 1)}),
                _fonte("x", "assunzione", {}, {"effetto": (0.1, 0.2)}),
                {**_fonte("x", "rct", {}, {"effetto": (0.1, 0.2)}), "sostiene_parametri": []},
                {**_fonte("x", "rct", {}, {"effetto": (0.1, 0.2)}), "stime": {"effetto": {"intervallo": [0.1, 0.2]}}}]
        for f in casi:
            with self.subTest(f=f), self.assertRaises(ValueError):
                evidence.intervalli_da_registro({"fonti": [f]}, self.IPOTESI)

    def test_registro_reale_usato_nell_analisi(self):
        iv = RIS["intervalli"]
        self.assertEqual(iv["effetto"]["origine"], "fonti")
        self.assertEqual(iv["costo_svantaggiati"]["origine"], "fonti")
        self.assertEqual(iv["saturazione"]["origine"], "ipotesi", "nessuna fonte stima la saturazione")
        for s in edu.scenari_train(50, 1, iv):
            self.assertTrue(iv["effetto"]["intervallo"][0] <= s["effetto"] <= iv["effetto"]["intervallo"][1])

    def test_estrapolazione_esce_dagli_intervalli_derivati(self):
        iv = RIS["intervalli"]
        lim = edu.limiti_estrapolazione(iv)
        for p, info in iv.items():
            self.assertLessEqual(lim[p][0], info["intervallo"][0])
            self.assertGreaterEqual(lim[p][1], info["intervallo"][1])
            self.assertGreaterEqual(lim[p][0], edu.LIMITI_FISICI[p][0])
        for s in edu.scenari_estrapolazione(30, 5, iv):
            self.assertTrue(any(not (iv[k]["intervallo"][0] <= v <= iv[k]["intervallo"][1]) for k, v in s.items()))

    def test_piani_precedenti_usano_le_ipotesi(self):
        pac = copy.deepcopy(PAC)
        del pac["analisi"]["intervalli"]
        self.assertTrue(all(v["origine"] == "ipotesi" for v in analysis.intervalli_effettivi(pac).values()))
        r = analysis.esegui(pac, con_studi=False, con_stabilita=False)
        self.assertNotIn("intervalli", r, "stessa forma del risultato 1.2.0: gli hash delle voci vecchie restano validi")
        self.assertTrue(r["limiti"][0].startswith("Tutti i parametri"))
        self.assertIn("saturazione", RIS["limiti"][0])
        pac["analisi"]["intervalli"] = {"fonte": "a_occhio"}
        with self.assertRaises(ValueError):
            analysis.intervalli_effettivi(pac)


INTESTAZIONE_COSTI = ("istituto;codice_meccanografico;tipo_istituto;gruppo;formato;ore_per_studente;studenti_per_gruppo;"
                      "costo_orario_personale_eur;oneri_e_indiretti_pct;altri_costi_per_studente_eur;documento;data_documento;verificato_da")


class TestRaccoltaCosti(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def _csv(self, *righe) -> Path:
        f = Path(self.tmp.name) / "costi.csv"
        f.write_text("﻿" + "\n".join((INTESTAZIONE_COSTI,) + righe) + "\n", encoding="utf-8")
        return f

    def test_costo_per_posto_e_formato_italiano(self):
        f = self._csv("IC Uno;MIIC000001;istituto_comprensivo;entrambi;individuale;20;1;35;32,7;0;prot. 1/2026;2026-09-01;DS",
                      "IC Due;MIIC000002;istituto_comprensivo;svantaggiati;piccolo_gruppo;30;3;79;40;7,50;delibera 4;2026-09-02;DSGA")
        righe = costi.leggi(f, oggi=datetime.date(2026, 10, 24))
        self.assertAlmostEqual(righe[0]["costo_per_posto_eur"], 35 * 1.327 * 20)
        self.assertAlmostEqual(righe[1]["costo_per_posto_eur"], 79 * 1.4 * 30 / 3 + 7.5)
        r = costi.riepilogo(righe)
        self.assertEqual((r["costo_svantaggiati"]["righe"], r["costo_altri"]["righe"]), (2, 1))
        prop = costi.proposta_fonte(righe, "preventivi_prova")
        self.assertEqual(prop["declassamenti"], {"imprecisione": 1}, "meno di 3 istituti")
        self.assertEqual(evidence.livello_fonte(prop), 3)
        iv = evidence.intervalli_da_registro({"fonti": [prop]}, edu.INTERVALLI_TRAIN)
        self.assertEqual(iv["costo_svantaggiati"]["origine"], "fonti")

    def test_righe_non_documentate_o_incoerenti(self):
        oggi = datetime.date(2026, 10, 24)
        for riga in ("IC;MI1;ic;entrambi;individuale;20;1;35;0;0;;2026-09-01;DS",            # senza documento
                     "IC;MI1;ic;entrambi;individuale;20;3;35;0;0;prot;2026-09-01;DS",        # individuale con 3 studenti
                     "IC;MI1;ic;entrambi;individuale;20;1;35;0;0;prot;2027-01-01;DS",        # data futura
                     "IC;MI1;ic;tutti;individuale;20;1;35;0;0;prot;2026-09-01;DS",           # gruppo sconosciuto
                     "IC;MI1;ic;entrambi;individuale;-5;1;35;0;0;prot;2026-09-01;DS"):       # ore negative
            with self.subTest(riga=riga), self.assertRaises(ValueError):
                costi.leggi(self._csv(riga), oggi=oggi)

    def test_riga_di_comando_non_sovrascrive(self):
        from cwm.__main__ import main
        f = self._csv("IC Uno;MIIC000001;istituto_comprensivo;entrambi;individuale;20;1;35;32,7;0;prot. 1/2026;2026-09-01;DS")
        out = Path(self.tmp.name) / "proposta.json"
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["costi", str(f), "--out", str(out)]), 0)
            self.assertEqual(main(["costi", str(f), "--out", str(out)]), 1)
        self.assertIn("stime", audit.carica_json_rigoroso(out.read_text(encoding="utf-8")))


class TestElicitazioneReale(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def _compila(self, valori_per_persona: list[list[str]], consenso="sì") -> Path:
        righe = elicitazione.modulo(edu.CRITERI, len(valori_per_persona)).splitlines()
        out = [righe[0]]
        for i, riga in enumerate(righe[1:]):
            pid, ruolo, data, cons, a, b, _ = riga.split(",")
            out.append(",".join([pid, "docente", "2026-10-01", consenso, a, b, valori_per_persona[i // 10][i % 10]]))
        f = Path(self.tmp.name) / "modulo.csv"
        f.write_text("\n".join(out) + "\n", encoding="utf-8")
        return f

    def test_modulo_ha_tutti_i_confronti(self):
        righe = elicitazione.modulo(edu.CRITERI, 2).splitlines()
        self.assertEqual(len(righe), 1 + 2 * 10)

    def test_importazione_e_giudizi_da_rivedere(self):
        coerente = ["1"] * 10
        incoerente = ["9", "1", "1", "1", "1/9", "1", "1", "1", "1", "1"]  # apprendimento >> equità ma equità >> accesso...
        f = self._compila([coerente, coerente, incoerente])
        doc, dia = elicitazione.importa(f, edu.CRITERI, "Facilitatore", "docs/elicitazione.md v1", oggi=datetime.date(2026, 10, 24))
        self.assertEqual(doc["natura"], "reale")
        self.assertEqual(elicitazione.valida_partecipanti(doc, edu.CRITERI, datetime.date(2026, 10, 24)), [])
        self.assertTrue(dia["P01"]["coerente"])
        self.assertFalse(dia["P03"]["coerente"])
        self.assertEqual(len(dia["P03"]["da_rivedere"]), 2)
        pac = copy.deepcopy(PAC)
        pac["partecipanti"] = doc
        with tempfile.TemporaryDirectory() as libero:
            self.assertTrue(audit.Registro(libero).controlli_uso(pac, RIS, "pilota_valutato")["consentito"])

    def test_senza_consenso_o_con_valori_fuori_scala(self):
        oggi = datetime.date(2026, 10, 24)
        with self.assertRaises(ValueError):
            elicitazione.importa(self._compila([["1"] * 10] * 3, consenso="no"), edu.CRITERI, "F", "P", oggi=oggi)
        with self.assertRaises(ValueError):
            elicitazione.importa(self._compila([["12"] + ["1"] * 9] * 3), edu.CRITERI, "F", "P", oggi=oggi)

    def test_preferenze_non_documentate(self):
        oggi = datetime.date(2026, 10, 24)
        doc = pac_con_partecipanti_reali()["partecipanti"]
        self.assertEqual(elicitazione.valida_partecipanti(doc, edu.CRITERI, oggi), [])
        for modifica in ({"natura": "sintetica"}, {"facilitatore": ""}, {"partecipanti": doc["partecipanti"][:2]}):
            with self.subTest(modifica=modifica):
                self.assertTrue(elicitazione.valida_partecipanti({**doc, **modifica}, edu.CRITERI, oggi))
        senza = {k: v for k, v in doc.items() if k != "natura"}
        self.assertTrue(elicitazione.valida_partecipanti(senza, edu.CRITERI, oggi))


if __name__ == "__main__":
    unittest.main()
