from video_downloader.media.filenames import FilenamePlanner, sanitize_filename


def test_sanitize_filename_replaces_illegal_characters():
    assert sanitize_filename('a<b>c:d"e/f\\g|h?i*j') == "a_b_c_d_e_f_g_h_i_j"


def test_sanitize_filename_strips_trailing_dots_and_spaces():
    assert sanitize_filename("My Title.  ") == "My Title"


def test_sanitize_filename_falls_back_when_empty_after_cleaning():
    assert sanitize_filename("...") == "download"


def test_sanitize_filename_prefixes_reserved_device_names():
    assert sanitize_filename("CON") == "_CON"
    assert sanitize_filename("com1") == "_com1"


def test_sanitize_filename_truncates_long_titles():
    long_title = "x" * 300
    result = sanitize_filename(long_title)
    assert len(result) <= 150


def test_filename_planner_uses_plain_name_when_no_collision(tmp_path):
    planner = FilenamePlanner()

    result = planner.plan(tmp_path, "My Video", "mp4")

    assert result == tmp_path / "My Video.mp4"


def test_filename_planner_numbers_on_collision(tmp_path):
    planner = FilenamePlanner()
    (tmp_path / "My Video.mp4").write_text("existing")

    result = planner.plan(tmp_path, "My Video", "mp4")

    assert result == tmp_path / "My Video (1).mp4"


def test_filename_planner_increments_past_multiple_collisions(tmp_path):
    planner = FilenamePlanner()
    (tmp_path / "My Video.mp4").write_text("existing")
    (tmp_path / "My Video (1).mp4").write_text("existing")

    result = planner.plan(tmp_path, "My Video", "mp4")

    assert result == tmp_path / "My Video (2).mp4"


def test_filename_planner_normalizes_extension_without_dot(tmp_path):
    planner = FilenamePlanner()

    result = planner.plan(tmp_path, "My Video", "mp4")

    assert result.suffix == ".mp4"
