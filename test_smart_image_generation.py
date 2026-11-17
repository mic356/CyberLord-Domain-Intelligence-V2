"""Regression tests for natural-language image generation routing."""
import app as cyberlord


def test_natural_image_requests_are_detected():
    assert cyberlord._image_generation_intent("Create an image of a futuristic city")
    assert cyberlord._image_generation_intent("Explain TCP handshake with a diagram")
    assert cyberlord._image_generation_intent("Turn your answer into an infographic")
    assert cyberlord._image_generation_intent("Edit this photo to use a dark background")
    assert cyberlord._image_generation_intent("I want a picture of a futuristic city")
    assert not cyberlord._image_generation_intent("Show me pictures of Lagos")
    assert not cyberlord._image_generation_intent("Explain TCP handshake step by step")


def test_image_batch_count_is_bounded():
    assert cyberlord._requested_image_count("Create 3 images of a network") == 3
    assert cyberlord._requested_image_count("Make several variations") == 4
    assert cyberlord._requested_image_count("Make 9 pictures") == 4
    assert cyberlord._requested_image_count("Create one logo") == 1
