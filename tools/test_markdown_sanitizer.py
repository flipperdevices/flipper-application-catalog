import unittest
from markdown import Markdown
from bundle import BasicTextExtension


class TestBasicTextExtension(unittest.TestCase):
    def setUp(self):
        self.md = Markdown(extensions=[BasicTextExtension()])

    def test_backtick_not_allowed(self):
        with self.assertRaises(Exception):
            self.md.convert("`example`")

    def test_reference_not_allowed(self):
        with self.assertRaises(Exception):
            self.md.convert("[example][example]")

    def test_link_not_allowed(self):
        with self.assertRaises(Exception):
            self.md.convert("[example](http://example.com)")

    def test_image_link_not_allowed(self):
        with self.assertRaises(Exception):
            self.md.convert("![example](http://example.com/image.png)")

    def test_image_reference_not_allowed(self):
        with self.assertRaises(Exception):
            self.md.convert("![example][ref]\n\n[ref]: http://example.com/image.png")

    def test_short_image_ref_not_allowed(self):
        with self.assertRaises(Exception):
            self.md.convert("![example]")

    def test_autolink_not_allowed(self):
        with self.assertRaises(Exception):
            self.md.convert("<http://example.com>")

    def test_automail_not_allowed(self):
        with self.assertRaises(Exception):
            self.md.convert("<mailto:example@example.com>")

    def test_html_not_allowed(self):
        with self.assertRaises(Exception):
            self.md.convert("<p>example</p>")

    def test_entity_not_allowed(self):
        with self.assertRaises(Exception):
            self.md.convert("&nbsp;")

    def test_hash_header_not_allowed(self):
        self.md.convert("#example")
        self.md.convert("##example")
        with self.assertRaises(Exception):
            self.md.convert("###example")

        with self.assertRaises(Exception):
            self.md.convert("#####example")

    def test_setext_header_not_allowed(self):
        with self.assertRaises(Exception):
            self.md.convert(
                """
                example
                =============
                """
            )

        with self.assertRaises(Exception):
            self.md.convert(
                """
                example
                -------------
                """
            )

    def test_code_block_not_allowed(self):
        with self.assertRaises(Exception):
            self.md.convert(
                """
                    example
                """
            )

    def test_horizontal_line_not_allowed(self):
        with self.assertRaises(Exception):
            self.md.convert("- - -")

        with self.assertRaises(Exception):
            self.md.convert("---------------------------------------")

        with self.assertRaises(Exception):
            self.md.convert("*****")

        with self.assertRaises(Exception):
            self.md.convert("***")

        with self.assertRaises(Exception):
            self.md.convert("* * *")

    def test_quote_not_allowed(self):
        with self.assertRaises(Exception):
            self.md.convert("> example")

        with self.assertRaises(Exception):
            self.md.convert(">> example")

    def test_list_unordered(self):
        self.md.convert("* Item \n * Item")

    def test_list_ordered(self):
        self.md.convert("1. Item \n 2. Item")

    def test_list_mixed(self):
        self.md.convert("1. Item\n2. Item\n    * Item\n    - Item\n3. Item")

    def test_bold(self):
        self.md.convert("**example**")
        self.md.convert("__example__")

    def test_italic(self):
        self.md.convert("*example*")
        self.md.convert("_example_")

    def test_bold_and_italic(self):
        self.md.convert("_**example**_")
        self.md.convert("**_example_**")
        self.md.convert("***example***")

