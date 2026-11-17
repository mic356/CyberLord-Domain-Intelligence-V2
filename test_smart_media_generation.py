"""Regression tests for CyberLord's natural-language media routing."""
import app as cyberlord


def test_file_requests_and_formats():
    assert cyberlord._file_generation_intent("Create a PDF report from your answer")
    assert cyberlord._file_generation_intent("Turn this into a PowerPoint presentation")
    assert cyberlord._file_generation_intent("Save this as an Excel spreadsheet")
    assert cyberlord._requested_file_format("Make a Word document") == "docx"
    assert cyberlord._requested_file_format("Create a CSV file") == "csv"
    assert cyberlord._requested_file_format("Create PowerPoint slides") == "pptx"
    assert not cyberlord._file_generation_intent("Explain how to create a PDF")


def test_video_requests_are_detected_without_triggering_how_to_questions():
    assert cyberlord._video_generation_intent("Generate a short video about cybersecurity")
    assert cyberlord._video_generation_intent("Can you make a video from this explanation?")
    assert not cyberlord._video_generation_intent("Explain how to create a video")
