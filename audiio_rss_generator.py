#!/usr/bin/env python3
"""
Generate RSS feed from Audiio browse page tracks
Includes separate image field for Klaviyo compatibility
"""

import urllib.request
import urllib.parse
import json
import xml.etree.ElementTree as ET
from datetime import datetime
from html import escape
import re

def fetch_tracks(per_page=100, max_pages=None):
    """Fetch tracks from Audiio API - continues until all tracks are fetched"""
    API_BASE = "https://audiio.com/api/tracks"
    all_tracks = []
    seen_ids = set()
    page = 1
    
    while True:
        # Stop if we've hit max_pages limit (if specified)
        if max_pages and page > max_pages:
            break
            
        params = {'limit': per_page, 'page': page}
        url = f"{API_BASE}?{urllib.parse.urlencode(params)}"
        
        try:
            with urllib.request.urlopen(url) as response:
                data = json.loads(response.read().decode())
                tracks = data.get('tracks', [])
                
                # If no tracks returned, we've reached the end
                if not tracks:
                    print(f"No more tracks found at page {page}")
                    break
                
                # Add tracks that we haven't seen before
                new_tracks = 0
                for track in tracks:
                    track_id = track.get('id')
                    if track_id and track_id not in seen_ids:
                        seen_ids.add(track_id)
                        all_tracks.append(track)
                        new_tracks += 1
                
                print(f"Page {page}: Found {len(tracks)} tracks ({new_tracks} new)")
                
                # If we got fewer tracks than requested, we're probably at the end
                if len(tracks) < per_page:
                    print(f"Reached end of catalog (got {len(tracks)} tracks, expected {per_page})")
                    break
                
                page += 1
                        
        except Exception as e:
            print(f"Error fetching page {page}: {e}")
            break
    
    return all_tracks

def get_track_url(track):
    """Generate track URL from slug"""
    artist_slug = track.get('artist', {}).get('slug')
    album_slug = track.get('album', {}).get('slug')
    track_slug = track.get('slug')

    if artist_slug and album_slug and track_slug:
        return f"https://audiio.com/{artist_slug}/{album_slug}/{track_slug}"
    elif track_slug:
        return f"https://audiio.com/track/{track_slug}"
    else:
        return "https://audiio.com/browse"

def get_image_url(track):
    """Extract image URL from track data"""
    # Try thumbnail first
    thumbnail = track.get('thumbnail', '')
    if thumbnail:
        if thumbnail.startswith('http'):
            return thumbnail
        elif thumbnail.startswith('/'):
            return f"https://d2pagzouz5kmpq.cloudfront.net{thumbnail}"
        else:
            return f"https://d2pagzouz5kmpq.cloudfront.net/{thumbnail}"
    
    # Try album image
    album = track.get('album', {})
    if isinstance(album, dict):
        img_path = album.get('image', '')
        if img_path:
            if img_path.startswith('http'):
                return img_path
            elif img_path.startswith('/'):
                return f"https://d2pagzouz5kmpq.cloudfront.net{img_path}"
            else:
                return f"https://d2pagzouz5kmpq.cloudfront.net/{img_path}"
    
    return ''

def format_duration(seconds):
    """Format duration in seconds to MM:SS"""
    if not seconds:
        return ''
    mins = seconds // 60
    secs = seconds % 60
    return f"{mins}:{secs:02d}"

def generate_rss(tracks, output_file='audiio_browse.rss'):
    """
    Generate RSS feed with image field
    Output file should match the GitHub Pages path if using GitHub Pages
    """
    root = ET.Element('rss')
    root.set('version', '2.0')
    root.set('xmlns:atom', 'http://www.w3.org/2005/Atom')
    root.set('xmlns:content', 'http://purl.org/rss/1.0/modules/content/')
    root.set('xmlns:media', 'http://search.yahoo.com/mrss/')
    
    channel = ET.SubElement(root, 'channel')
    
    ET.SubElement(channel, 'title').text = 'Audiio Browse - Complete Catalog'
    ET.SubElement(channel, 'description').text = "Complete music catalog from Audiio's browse page"
    ET.SubElement(channel, 'link').text = 'https://audiio.com/browse'
    ET.SubElement(channel, 'language').text = 'en-us'
    # Format: Wed, 07 Jan 2026 10:05:07 (RSS 2.0 format)
    from datetime import timezone
    now = datetime.now(timezone.utc)
    ET.SubElement(channel, 'lastBuildDate').text = now.strftime('%a, %d %b %Y %H:%M:%S +0000')
    
    atom_link = ET.SubElement(channel, 'atom:link')
    atom_link.set('href', 'https://audiio.com/browse')
    atom_link.set('rel', 'self')
    atom_link.set('type', 'application/rss+xml')
    
    for track in tracks:
        item = ET.SubElement(channel, 'item')
        
        # Extract data
        artist = track.get('artist', {})
        album = track.get('album', {})
        artist_name = artist.get('name', '') if isinstance(artist, dict) else ''
        album_name = album.get('name', '') if isinstance(album, dict) else ''
        genres = track.get('genres', [])
        genre_str = ', '.join(genres) if genres else ''
        bpm = track.get('bpm', '')
        duration = format_duration(track.get('duration', 0))
        
        # Title (just track name, no artist)
        title = track.get('title', 'Untitled')
        ET.SubElement(item, 'title').text = title
        
        # Link
        track_url = get_track_url(track)
        ET.SubElement(item, 'link').text = track_url
        
        # GUID
        track_id = track.get('id')
        guid = ET.SubElement(item, 'guid')
        guid.set('isPermaLink', 'false')
        guid.text = f"https://audiio.com/track/{track_id}" if track_id else track_url
        
        # Image URL (separate field for Klaviyo)
        image_url = get_image_url(track)
        if image_url:
            # Add as media:thumbnail (standard RSS extension)
            media_thumbnail = ET.SubElement(item, 'media:thumbnail')
            media_thumbnail.set('url', image_url)
            # Also add as simple <image> tag for compatibility
            image_elem = ET.SubElement(item, 'image')
            image_elem.text = image_url
        
        # Separate clean fields for Klaviyo (no HTML)
        ET.SubElement(item, 'artist').text = artist_name
        ET.SubElement(item, 'album').text = album_name
        ET.SubElement(item, 'duration').text = duration
        ET.SubElement(item, 'bpm').text = str(bpm) if bpm else ''
        ET.SubElement(item, 'genres').text = genre_str
        
        # Description (keep for backwards compatibility, but Klaviyo should use separate fields)
        desc_html = f"""<p><strong>Artist:</strong> {escape(artist_name)}</p>
<p><strong>Album:</strong> {escape(album_name)}</p>
<p><strong>Genres:</strong> {escape(genre_str)}</p>
<p><strong>BPM:</strong> {escape(str(bpm))}</p>
<p><strong>Duration:</strong> {escape(duration)}</p>"""
        
        if image_url:
            desc_html += f'<p><img src="{escape(image_url)}" alt="Track artwork" /></p>'
        
        ET.SubElement(item, 'description').text = desc_html
        
        # Content encoded
        content_elem = ET.SubElement(item, 'content:encoded')
        content_elem.text = f"<![CDATA[{desc_html}]]>"
        
        # PubDate
        pub_date = track.get('created_at', '')
        if pub_date:
            try:
                # Try to parse and format date
                dt = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
                ET.SubElement(item, 'pubDate').text = dt.strftime('%a, %d %b %Y %H:%M:%S %z')
            except:
                ET.SubElement(item, 'pubDate').text = pub_date
        
        # Enclosure (audio file)
        audio_url = track.get('audio_url', '')
        if audio_url:
            enclosure = ET.SubElement(item, 'enclosure')
            enclosure.set('url', audio_url)
            enclosure.set('type', 'audio/mpeg')
        
        # Categories (genres)
        for genre in genres:
            if genre:
                ET.SubElement(item, 'category').text = genre
    
    # Write to file
    tree = ET.ElementTree(root)
    ET.indent(tree, space='  ')
    tree.write(output_file, encoding='utf-8', xml_declaration=True)
    print(f"RSS feed generated: {output_file} ({len(tracks)} tracks)")

if __name__ == '__main__':
    print("Fetching tracks from Audiio API...")
    # Fetch all tracks - no max_pages limit, will continue until API returns empty
    tracks = fetch_tracks(per_page=100, max_pages=None)
    print(f"Total tracks found: {len(tracks)}")
    
    print("Generating RSS feed...")
    generate_rss(tracks)
    print("Done!")
