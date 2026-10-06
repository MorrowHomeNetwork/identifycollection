"""
Tests for the heart of the project: photographs, answers, review, export.

They follow the journey in the order a museum lives it. Each test gets its
own empty scratch folder for pictures, so nothing touches real data.
"""

import csv
import io
import shutil
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from . import workflow
from .images import NotAnImage
from .intake import add_photograph, add_samples, remove_samples
from .models import AccessionEvent, DeaccessionEvent, Evidence, Mystery, Submission

User = get_user_model()


def picture(name="scan.png", size=(1200, 900), mode="RGB", fmt="PNG", shade=120):
    """A small made-up scan, as the browser would upload it."""
    buffer = io.BytesIO()
    Image.new(mode, size, shade).save(buffer, fmt)
    return SimpleUploadedFile(name, buffer.getvalue())


class ScratchMedia(TestCase):
    """Gives each test a private, empty folder to keep pictures in."""

    def setUp(self):
        super().setUp()
        folder = Path(tempfile.mkdtemp(prefix="ic-test-"))
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        override = override_settings(MEDIA_ROOT=folder / "media", FILE_UPLOAD_TEMP_DIR=folder / "tmp")
        override.enable()
        self.addCleanup(override.disable)
        self.staff = User(username="registrar", is_staff=True)
        self.staff.set_unusable_password()  # these tests sign in directly; skipping the slow password step keeps them quick
        self.staff.save()

    def on_show(self, **details) -> Mystery:
        photo, _created = add_photograph(picture(shade=len(Mystery.objects.all()) + 60), self.staff, **details)
        photo.status = Mystery.Status.PUBLISHED
        photo.save()
        return photo

    def answer(self, photo, **changes):
        form = {
            "person_name": "Edith Marlow", "confidence": "certain",
            "box_x": "0.25", "box_y": "0.2", "box_w": "0.1", "box_h": "0.2",
            "evidence_kind": "testimony", "evidence_text": "She was my grandmother.", "consent": "on",
        }  # fmt: skip
        form.update(changes)
        return self.client.post(photo.get_absolute_url(), {key: value for key, value in form.items() if value is not None})


class AddingPhotographsTests(ScratchMedia):
    def test_a_scan_becomes_a_hidden_draft_with_two_browser_pictures(self):
        photo, created = add_photograph(picture("1987.12.4.png", size=(5000, 3000)), self.staff)
        self.assertTrue(created)
        self.assertEqual(photo.status, Mystery.Status.DRAFT)
        self.assertEqual((photo.width, photo.height), (5000, 3000))
        self.assertEqual(photo.original_name, "1987.12.4.png")
        with Image.open(photo.web_path) as web, Image.open(photo.thumb_path) as thumb:
            self.assertEqual(web.format, "JPEG")
            self.assertEqual(max(web.size), 4000)
            self.assertEqual(max(thumb.size), 520)

    def test_archival_formats_are_understood(self):
        for mode, fmt, name in [("I;16", "TIFF", "a.tif"), ("L", "TIFF", "b.tif"), ("RGBA", "PNG", "c.png"), ("CMYK", "JPEG", "d.jpg")]:
            with self.subTest(kind=f"{mode} {fmt}"):
                shade = 30000 if mode == "I;16" else 130
                photo, _created = add_photograph(picture(name, mode=mode, fmt=fmt, shade=shade), self.staff)
                with Image.open(photo.web_path) as web:
                    self.assertIn(web.mode, {"L", "RGB"})

    def test_the_same_file_twice_is_added_once(self):
        first, _ = add_photograph(picture(), self.staff)
        second, created = add_photograph(picture(), self.staff)
        self.assertFalse(created)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Mystery.objects.count(), 1)

    def test_a_file_that_is_not_a_picture_is_refused_and_leaves_nothing_behind(self):
        with self.assertRaises(NotAnImage):
            add_photograph(SimpleUploadedFile("notes.jpg", b"not a picture at all"), self.staff)
        self.assertEqual(Mystery.objects.count(), 0)

    def test_staff_can_add_through_the_page(self):
        self.client.force_login(self.staff)
        answer = self.client.post(reverse("photo_upload"), {"file": picture("x.png")}, headers={"X-Requested-With": "fetch"})
        self.assertEqual(answer.json()["results"][0]["ok"], True)
        plain = self.client.post(reverse("photo_upload"), {"file": [picture("y.png", shade=10), SimpleUploadedFile("z.jpg", b"junk")]})
        self.assertRedirects(plain, reverse("photos"))
        self.assertEqual(Mystery.objects.count(), 2)

    def test_visitors_cannot_add_photographs(self):
        response = self.client.post(reverse("photo_upload"), {"file": picture()})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Mystery.objects.count(), 0)

    def test_practice_photographs_can_be_added_and_removed_completely(self):
        self.assertEqual(add_samples(self.staff), 6)
        self.assertEqual(add_samples(self.staff), 0)  # a second press adds nothing
        sample = Mystery.objects.filter(is_sample=True).first()
        sample.status = Mystery.Status.PUBLISHED
        sample.save()
        self.answer(sample)
        workflow.accept(Submission.objects.get(), self.staff)
        real = self.on_show()
        self.assertEqual(remove_samples(), 6)
        self.assertEqual(list(Mystery.objects.all()), [real])
        self.assertEqual(Submission.objects.count() + AccessionEvent.objects.count(), 0)


class WhatVisitorsSeeTests(ScratchMedia):
    def test_nothing_is_public_until_staff_put_it_on_show(self):
        draft, _ = add_photograph(picture(), self.staff)
        with self.assertLogs("django.request", level="WARNING"):
            self.assertEqual(self.client.get(draft.get_absolute_url()).status_code, 404)
            self.assertEqual(self.client.get(reverse("web_image", args=[draft.pk])).status_code, 404)
            self.assertEqual(self.client.get(reverse("thumb_image", args=[draft.pk])).status_code, 404)
        self.assertNotContains(self.client.get(reverse("gallery")), draft.get_absolute_url())

    def test_staff_put_photographs_on_show_and_take_them_off(self):
        draft, _ = add_photograph(picture(), self.staff)
        self.client.force_login(self.staff)
        self.client.post(reverse("photos"), {"action": "publish", "photo": [draft.pk]})
        self.client.logout()
        self.assertContains(self.client.get(reverse("gallery")), draft.get_absolute_url())
        self.assertEqual(self.client.get(reverse("web_image", args=[draft.pk])).status_code, 200)
        self.client.force_login(self.staff)
        self.client.post(reverse("photos"), {"action": "retire", "photo": [draft.pk]})
        self.client.logout()
        self.assertNotContains(self.client.get(reverse("gallery")), draft.get_absolute_url())

    def test_staff_can_describe_a_photograph(self):
        photo = self.on_show()
        self.client.force_login(self.staff)
        self.client.post(reverse("photo_edit", args=[photo.pk]), {"object_id": "1987.12.4", "title": "Harvest crew", "date_text": "about 1920", "description": ""})
        self.client.logout()
        page = self.client.get(photo.get_absolute_url())
        self.assertContains(page, "Harvest crew")
        self.assertContains(page, "Object 1987.12.4")


class SendingAnAnswerTests(ScratchMedia):
    def setUp(self):
        super().setUp()
        self.photo = self.on_show(title="Harvest crew")

    def test_an_answer_with_a_mark_and_testimony_waits_for_review_and_is_not_public(self):
        response = self.answer(self.photo, contributor_name="Ruth", credit_ok="on")
        sent = Submission.objects.get()
        self.assertRedirects(response, reverse("thanks", args=[sent.reference]))
        self.assertEqual(sent.status, Submission.Status.PENDING)
        self.assertEqual((sent.box_x, sent.box_w), (0.25, 0.1))
        evidence = sent.evidence.get()
        self.assertEqual(evidence.kind, Evidence.Kind.TESTIMONY)
        self.assertTrue(evidence.consent_given)
        self.assertContains(self.client.get(reverse("thanks", args=[sent.reference])), sent.reference)
        self.assertNotContains(self.client.get(self.photo.get_absolute_url()), "Edith Marlow")

    def test_what_is_missing_is_explained_and_nothing_is_saved(self):
        cases = {
            "no mark and no description": ({"box_x": None, "box_y": None, "box_w": None, "box_h": None}, "describe here where they are"),
            "testimony without saying how": ({"evidence_text": ""}, "say how you know"),
            "testimony without agreement": ({"consent": None}, "may keep your account"),
            "document without a file": ({"evidence_kind": "document", "rights": "on"}, "attach the document"),
            "another record without saying which": ({"evidence_kind": "cross_reference", "evidence_text": ""}, "which other record"),
            "contact wanted but no address": ({"contact_ok": "on"}, "give an email address or phone number"),
            "a mark outside the picture": ({"box_x": "0.95", "box_w": "0.4"}, "mark the person again"),
            "no name": ({"person_name": ""}, "This field is required"),
        }
        for label, (changes, expected) in cases.items():
            with self.subTest(case=label):
                response = self.answer(self.photo, **changes)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, expected)
        self.assertEqual(Submission.objects.count(), 0)

    def test_a_description_can_stand_in_for_a_mark(self):
        self.answer(self.photo, box_x=None, box_y=None, box_w=None, box_h=None, position_note="back row, far left")
        sent = Submission.objects.get()
        self.assertFalse(sent.has_box)
        self.assertEqual(sent.position_note, "back row, far left")

    def test_a_document_is_kept_privately_for_staff(self):
        scan = SimpleUploadedFile("yearbook 1952.pdf", b"%PDF-1.4 pretend")
        self.answer(self.photo, evidence_kind="document", evidence_text="", evidence_file=scan, rights="on", consent=None)
        evidence = Evidence.objects.get()
        self.assertTrue(evidence.rights_acknowledged)
        self.assertEqual(evidence.file_name, "yearbook 1952.pdf")
        self.assertTrue(evidence.file_path.is_file())
        self.assertNotIn("yearbook", evidence.file)  # stored under a random name
        link = reverse("evidence_file", args=[evidence.pk])
        self.assertEqual(self.client.get(link).status_code, 302)  # visitors are sent to sign in
        self.client.force_login(self.staff)
        self.assertEqual(b"".join(self.client.get(link).streaming_content), b"%PDF-1.4 pretend")

    def test_unsuitable_attachments_are_refused(self):
        program = SimpleUploadedFile("surprise.exe", b"MZ")
        response = self.answer(self.photo, evidence_kind="document", evidence_file=program, rights="on")
        self.assertContains(response, "attach a PDF or a picture")
        self.assertEqual(Submission.objects.count(), 0)

    def test_form_filling_programs_are_turned_away(self):
        self.answer(self.photo, website="http://spam.example")
        self.assertEqual(Submission.objects.count(), 0)

    def test_answers_cannot_be_sent_about_a_photograph_that_is_not_on_show(self):
        self.photo.status = Mystery.Status.RETIRED
        self.photo.save()
        with self.assertLogs("django.request", level="WARNING"):
            self.assertEqual(self.answer(self.photo).status_code, 404)
        self.assertEqual(Submission.objects.count(), 0)


class ReviewTests(ScratchMedia):
    def setUp(self):
        super().setUp()
        self.photo = self.on_show(title="Harvest crew", object_id="1987.12.4")
        self.answer(self.photo, contributor_name="Ruth Marlow", contributor_contact="ruth@example.org", contact_ok="on", credit_ok="on")
        self.sent = Submission.objects.get()
        self.page = reverse("submission", args=[self.sent.reference])

    def decide(self, action, note="", **extra):
        self.client.force_login(self.staff)
        response = self.client.post(self.page, {"action": action, "note": note, **extra})
        self.client.logout()
        self.sent.refresh_from_db()
        return response

    def test_review_pages_are_for_staff_only(self):
        visitor = User.objects.create_user("someone", password="lantern-slide-archive-1908")
        for address in (reverse("queue"), self.page, reverse("photos"), reverse("export"), reverse("export_csv")):
            with self.subTest(address=address):
                self.assertEqual(self.client.get(address).status_code, 302)
                self.client.force_login(visitor)
                with self.assertLogs("django.request", level="WARNING"):
                    self.assertEqual(self.client.get(address).status_code, 403)
                self.client.logout()

    def test_the_queue_shows_what_is_waiting(self):
        self.client.force_login(self.staff)
        self.assertContains(self.client.get(reverse("queue")), self.sent.reference)
        page = self.client.get(self.page)
        self.assertContains(page, "She was my grandmother.")
        self.assertContains(page, "ruth@example.org")

    def test_accepting_makes_it_public_and_records_who_decided(self):
        self.decide("accept", "Matches the family's copy.")
        self.assertEqual(self.sent.status, Submission.Status.ACCEPTED)
        event = AccessionEvent.objects.get()
        self.assertEqual((event.by, event.note), (self.staff, "Matches the family's copy."))
        page = self.client.get(self.photo.get_absolute_url())
        self.assertContains(page, "Edith Marlow")
        self.assertContains(page, "identified by Ruth Marlow")
        self.assertNotContains(page, "ruth@example.org")
        self.assertContains(self.client.get(reverse("gallery")), "1 named so far")

    def test_declining_keeps_it_private(self):
        self.decide("reject", "Too young to be her.")
        self.assertEqual(self.sent.status, Submission.Status.REJECTED)
        self.assertEqual(AccessionEvent.objects.count(), 0)
        self.assertNotContains(self.client.get(self.photo.get_absolute_url()), "Edith Marlow")

    def test_withdrawing_needs_a_reason_and_keeps_the_history(self):
        self.decide("accept")
        self.decide("withdraw", "   ")
        self.assertEqual(self.sent.status, Submission.Status.ACCEPTED)  # no reason, no withdrawal
        self.decide("withdraw", "The family says this is her sister.")
        self.assertEqual(self.sent.status, Submission.Status.WITHDRAWN)
        self.assertEqual(DeaccessionEvent.objects.get().reason, "The family says this is her sister.")
        self.assertEqual(AccessionEvent.objects.count(), 1)  # the original acceptance is still on record
        self.assertNotContains(self.client.get(self.photo.get_absolute_url()), "Edith Marlow")

    def test_a_withdrawal_can_be_reversed(self):
        self.decide("accept")
        self.decide("withdraw", "Doubt raised.")
        self.decide("accept", "Doubt resolved by the 1921 census.")
        self.assertEqual(self.sent.status, Submission.Status.ACCEPTED)
        self.assertEqual((AccessionEvent.objects.count(), DeaccessionEvent.objects.count()), (2, 1))
        self.assertContains(self.client.get(self.photo.get_absolute_url()), "Edith Marlow")

    def test_only_sensible_moves_are_allowed(self):
        with self.assertRaises(workflow.NotAllowed):
            workflow.withdraw(self.sent, self.staff, "never accepted")
        workflow.accept(self.sent, self.staff)
        with self.assertRaises(workflow.NotAllowed):
            workflow.accept(self.sent, self.staff)
        with self.assertRaises(workflow.NotAllowed):
            workflow.reject(self.sent, self.staff)

    def test_a_contributors_details_can_be_erased_without_losing_the_identification(self):
        self.decide("accept")
        self.decide("remove_personal_data")  # without the confirming tick: nothing happens
        self.assertEqual(self.sent.contributor_name, "Ruth Marlow")
        self.decide("remove_personal_data", confirm="yes")
        self.assertEqual((self.sent.contributor_name, self.sent.contributor_contact, self.sent.contact_ok), ("", "", False))
        self.assertIsNotNone(self.sent.personal_data_removed_at)
        page = self.client.get(self.photo.get_absolute_url())
        self.assertContains(page, "Edith Marlow")
        self.assertNotContains(page, "Ruth Marlow")

    def test_accepted_work_cannot_be_deleted_out_from_under_the_record(self):
        from django.db.models import ProtectedError

        self.decide("accept")
        with self.assertRaises(ProtectedError):
            self.sent.delete()
        with self.assertRaises(ProtectedError):
            self.photo.delete()


class ExportTests(ScratchMedia):
    def rows(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("export_csv"))
        self.assertEqual(response.status_code, 200)
        text = response.content.decode("utf-8")
        self.assertTrue(text.startswith("\ufeff"))
        return list(csv.DictReader(io.StringIO(text.lstrip("\ufeff"))))

    def test_export_holds_what_was_accepted_and_what_was_withdrawn_and_nothing_else(self):
        photo, _ = add_photograph(picture("1987.12.4.png", size=(4000, 2000)), self.staff, object_id="1987.12.4", title="Harvest crew")
        photo.status = Mystery.Status.PUBLISHED
        photo.save()
        self.answer(photo, person_name="Edith Marlow", contributor_name="Ruth", credit_ok="on")
        self.answer(photo, person_name="Zo\u00eb Okafor")
        self.answer(photo, person_name="Never Reviewed")
        self.answer(photo, person_name="Declined Person")
        edith, zoe, _pending, declined = Submission.objects.order_by("id")
        workflow.accept(edith, self.staff)
        workflow.accept(zoe, self.staff)
        workflow.withdraw(zoe, self.staff, "Wrong generation.")
        workflow.reject(declined, self.staff)

        rows = self.rows()
        self.assertEqual([(row["person_name"], row["status"]) for row in rows], [("Edith Marlow", "accepted"), ("Zo\u00eb Okafor", "withdrawn")])
        first = rows[0]
        self.assertEqual(first["object_id"], "1987.12.4")
        self.assertEqual(first["scan_file_name"], "1987.12.4.png")
        self.assertEqual(first["w3c_selector"], "xywh=pixel:1000,400,400,400")  # in pixels of the ORIGINAL scan
        self.assertEqual((first["credited_to"], first["accepted_by"]), ("Ruth", "registrar"))
        self.assertEqual(rows[1]["withdrawal_reason"], "Wrong generation.")
        self.assertEqual(rows[1]["withdrawn_by"], "registrar")

    def test_identifications_are_also_available_in_the_open_annotation_standard(self):
        photo = self.on_show(object_id="1987.12.4")
        self.answer(photo)
        note = Submission.objects.get().web_annotation()
        self.assertEqual(note["type"], "Annotation")
        self.assertEqual(note["body"][0]["value"], "Edith Marlow")
        self.assertEqual(note["target"]["source"], "1987.12.4")
        self.assertEqual(note["target"]["selector"]["value"], "xywh=pixel:300,180,120,180")
