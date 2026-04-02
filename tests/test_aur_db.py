import pytest
from sven.db.aur_db import AURDB

def test_aurdb_search(mocker, tmp_path):
    db = AURDB(cache_dir=str(tmp_path))
    
    mock_response = mocker.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "version": 5,
        "type": "search",
        "resultcount": 1,
        "results": [
            {"Name": "spotify", "Version": "1.2.25", "Description": "Music service"}
        ]
    }
    mocker.patch("requests.get", return_value=mock_response)
    
    res = db.search("spotify")
    assert len(res) == 1
    assert res[0].name == "spotify"
    assert res[0].version == "1.2.25"
    assert res[0].repo == "aur"

def test_aurdb_info(mocker, tmp_path):
    db = AURDB(cache_dir=str(tmp_path))
    
    mock_response = mocker.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "version": 5,
        "type": "multiinfo",
        "resultcount": 1,
        "results": [
            {
                "Name": "spotify", 
                "Version": "1.2.25",
                "Description": "Music",
                "Depends": ["alsa-lib"]
            }
        ]
    }
    mocker.patch("requests.get", return_value=mock_response)
    
    pkg = db.info("spotify")
    assert pkg is not None
    assert pkg.name == "spotify"
    assert "alsa-lib" in pkg.deps
    
def test_aurdb_info_not_found(mocker, tmp_path):
    db = AURDB(cache_dir=str(tmp_path))
    mock_response = mocker.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "version": 5,
        "type": "multiinfo", 
        "resultcount": 0,
        "results": []
    }
    mocker.patch("requests.get", return_value=mock_response)
    
    pkg = db.info("doesnotexist")
    assert pkg is None
