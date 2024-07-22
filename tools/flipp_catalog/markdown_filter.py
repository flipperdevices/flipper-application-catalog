from markdown.extensions import Extension
from markdown.preprocessors import HtmlBlockPreprocessor


# A Markdown extension that removes all but basic text formatting
class BasicFormattingEnforcingExtension(Extension):
    ERROR_MESSAGE = "Markdown element '{}' is not allowed"
    MAX_HEADER_DEPTH = 2

    def __init__(self, **kwargs):
        # override the html preprocessor to avoid html text conversion so as not to be skipped by HtmlInlineProcessor
        HtmlBlockPreprocessor.run = lambda _self, lines: lines
        super().__init__(**kwargs)

    @staticmethod
    def handleMatch(element_type):
        def wrapper(instance, m):
            raise Exception(
                BasicFormattingEnforcingExtension.ERROR_MESSAGE.format(element_type)
            )

        return wrapper

    @staticmethod
    def not_supported_reference_processor_wrapper(instance, method):
        def wrapper(parent, block):
            res = method(parent, block)

            if res:
                raise Exception(
                    BasicFormattingEnforcingExtension.ERROR_MESSAGE.format("Reference")
                )

            return False

        return wrapper

    @staticmethod
    def not_supported_block_processor_wrapper(instance, name=None):
        def wrapper(parent, block):
            raise Exception(
                BasicFormattingEnforcingExtension.ERROR_MESSAGE.format(
                    name or instance.__class__.__name__
                )
            )

        return wrapper

    @staticmethod
    def not_supported_header_depth_processor_wrapper(instance):
        orig_run = instance.run

        def wrapper(parent, blocks):
            if m := instance.RE.match(blocks[0]):
                header_depth = len(m.group("level"))
                if header_depth > BasicFormattingEnforcingExtension.MAX_HEADER_DEPTH:
                    raise Exception(
                        f"Markdown element 'Header Depth' max level {BasicFormattingEnforcingExtension.MAX_HEADER_DEPTH} exceeded"
                    )

            return orig_run(parent, blocks)

        return wrapper

    def extendMarkdown(self, md):
        for md_element in (
            "backtick",
            # "reference",
            # "link",
            "image_link",
            "image_reference",
            "short_reference",
            "short_image_ref",
            # "autolink",
            "automail",
            "html",
            "entity",
        ):
            md.inlinePatterns[md_element].handleMatch = self.handleMatch(
                md_element.capitalize()
            )

        hash_header_processor = md.parser.blockprocessors["hashheader"]
        hash_header_processor.run = self.not_supported_header_depth_processor_wrapper(
            instance=hash_header_processor
        )

        setext_header_processor = md.parser.blockprocessors["setextheader"]
        setext_header_processor.run = self.not_supported_block_processor_wrapper(
            instance=setext_header_processor, name="Setext Header"
        )

        code_block_processor = md.parser.blockprocessors["code"]
        code_block_processor.run = self.not_supported_block_processor_wrapper(
            instance=code_block_processor, name="Code Block"
        )

        hr_processor = md.parser.blockprocessors["hr"]
        hr_processor.run = self.not_supported_block_processor_wrapper(
            instance=hr_processor, name="Horizontal Line"
        )

        quote_processor = md.parser.blockprocessors["quote"]
        quote_processor.run = self.not_supported_block_processor_wrapper(
            instance=quote_processor, name="Quote"
        )

        reference_processor = md.parser.blockprocessors["reference"]
        reference_processor.run = self.not_supported_reference_processor_wrapper(
            instance=reference_processor, method=reference_processor.run
        )
