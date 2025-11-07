"""
Sitemap generation engine for creating XML sitemaps from document entries.

This module handles the creation of XML sitemap files conforming to the
sitemaps.org protocol, including support for splitting large sitemaps
and gzip compression.
"""

import gzip
from datetime import datetime
from pathlib import Path
from typing import List, Optional, AsyncIterator
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom

from loguru import logger

from .types import SitemapEntry, SitemapConfig, CoreResult
from .exceptions import ProcessingError


class SitemapGenerator:
    """
    Generates XML sitemap files from sitemap entries.
    
    Handles XML generation, file splitting when URL limits are exceeded,
    and optional gzip compression of output files.
    """
    
    def __init__(self, config: SitemapConfig):
        """
        Initialize the sitemap generator.
        
        Args:
            config: Sitemap configuration settings
        """
        self.config = config
        self.output_dir = Path(config.output_dir)
        self.max_urls_per_file = config.max_urls_per_file
        self.compress = config.compress
        self.base_url = config.base_url.rstrip('/')
        
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.debug(
            "SitemapGenerator initialized",
            output_dir=str(self.output_dir),
            max_urls_per_file=self.max_urls_per_file,
            compress=self.compress
        )
    
    async def generate_sitemaps(
        self, 
        sitemap_entries: AsyncIterator[SitemapEntry], 
        core_name: str
    ) -> List[Path]:
        """
        Generate sitemap files from an async iterator of sitemap entries.
        
        Args:
            sitemap_entries: Async iterator yielding SitemapEntry objects
            core_name: Name of the core being processed (used for filenames)
            
        Returns:
            List of generated sitemap file paths
            
        Raises:
            ProcessingError: If sitemap generation fails
        """
        try:
            logger.info(
                "Starting sitemap generation",
                core_name=core_name,
                output_dir=str(self.output_dir)
            )
            
            generated_files = []
            current_entries = []
            file_counter = 1
            total_entries = 0
            
            async for entry in sitemap_entries:
                current_entries.append(entry)
                total_entries += 1
                
                # Check if we need to split the sitemap
                if len(current_entries) >= self.max_urls_per_file:
                    sitemap_file = await self._create_sitemap_file(
                        current_entries, 
                        core_name, 
                        file_counter
                    )
                    generated_files.append(sitemap_file)
                    
                    logger.debug(
                        "Sitemap file created",
                        file=sitemap_file.name,
                        entries=len(current_entries),
                        total_processed=total_entries
                    )
                    
                    current_entries = []
                    file_counter += 1
            
            # Handle remaining entries
            if current_entries:
                sitemap_file = await self._create_sitemap_file(
                    current_entries, 
                    core_name, 
                    file_counter
                )
                generated_files.append(sitemap_file)
                
                logger.debug(
                    "Final sitemap file created",
                    file=sitemap_file.name,
                    entries=len(current_entries),
                    total_processed=total_entries
                )
            
            # Create sitemap index if multiple files were generated
            if len(generated_files) > 1:
                index_file = await self._create_sitemap_index(generated_files, core_name)
                generated_files.insert(0, index_file)  # Add index at the beginning
                
                logger.info(
                    "Sitemap index created",
                    index_file=index_file.name,
                    sitemap_count=len(generated_files) - 1
                )
            
            logger.info(
                "Sitemap generation completed",
                core_name=core_name,
                total_entries=total_entries,
                files_generated=len(generated_files)
            )
            
            return generated_files
            
        except Exception as e:
            logger.error(
                "Sitemap generation failed",
                core_name=core_name,
                error=str(e)
            )
            raise ProcessingError(f"Failed to generate sitemaps for core {core_name}: {e}") from e
    
    async def _create_sitemap_file(
        self, 
        entries: List[SitemapEntry], 
        core_name: str, 
        file_number: int
    ) -> Path:
        """
        Create a single sitemap XML file from a list of entries.
        
        Args:
            entries: List of sitemap entries to include
            core_name: Name of the core (used for filename)
            file_number: Sequential number for the file
            
        Returns:
            Path to the created sitemap file
        """
        # Generate filename
        if file_number == 1 and len(entries) < self.max_urls_per_file:
            # Single file, use simple name
            filename = f"sitemap_{core_name}.xml"
        else:
            # Multiple files, use numbered names
            filename = f"sitemap_{core_name}_{file_number}.xml"
        
        file_path = self.output_dir / filename
        
        # Generate XML content
        xml_content = self._create_sitemap_xml(entries)
        
        # Write to file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(xml_content)
        
        # Compress if requested
        if self.compress:
            compressed_path = await self._compress_file(file_path)
            file_path.unlink()  # Remove uncompressed file
            return compressed_path
        
        return file_path
    
    def _create_sitemap_xml(self, entries: List[SitemapEntry]) -> str:
        """
        Create XML sitemap content from a list of entries.
        
        Args:
            entries: List of sitemap entries
            
        Returns:
            Formatted XML string
        """
        # Create root element with namespace
        urlset = Element('urlset')
        urlset.set('xmlns', 'http://www.sitemaps.org/schemas/sitemap/0.9')
        
        for entry in entries:
            url_element = SubElement(urlset, 'url')
            
            # Add location (required)
            loc = SubElement(url_element, 'loc')
            loc.text = entry.url
            
            # Add last modification date if available
            if entry.last_modified:
                lastmod = SubElement(url_element, 'lastmod')
                # Format as ISO 8601 date (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS+00:00)
                lastmod.text = entry.last_modified.strftime('%Y-%m-%dT%H:%M:%S+00:00')
            
            # Add change frequency
            if entry.changefreq:
                changefreq = SubElement(url_element, 'changefreq')
                changefreq.text = entry.changefreq
        
        # Convert to string with pretty formatting
        rough_string = tostring(urlset, encoding='unicode')
        reparsed = minidom.parseString(rough_string)
        
        # Get pretty printed XML, remove first line (XML declaration will be added manually)
        pretty_xml = reparsed.toprettyxml(indent="  ", encoding=None)
        lines = pretty_xml.split('\n')[1:]  # Skip XML declaration line
        
        # Add proper XML declaration and join lines
        xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>'
        return xml_declaration + '\n' + '\n'.join(line for line in lines if line.strip())
    
    async def _compress_file(self, file_path: Path) -> Path:
        """
        Compress a file using gzip compression.
        
        Args:
            file_path: Path to the file to compress
            
        Returns:
            Path to the compressed file
        """
        compressed_path = file_path.with_suffix(file_path.suffix + '.gz')
        
        with open(file_path, 'rb') as f_in:
            with gzip.open(compressed_path, 'wb') as f_out:
                f_out.writelines(f_in)
        
        logger.debug(
            "File compressed",
            original=file_path.name,
            compressed=compressed_path.name,
            original_size=file_path.stat().st_size,
            compressed_size=compressed_path.stat().st_size
        )
        
        return compressed_path
    
    async def create_global_sitemap_index(self, sitemap_files: List[Path]) -> Path:
        """
        Create a global sitemap index file referencing all sitemap files from all cores.
        
        This is a public method to create the main sitemap index that references all generated sitemaps.
        Uses the configured output_name from SitemapConfig.
        
        Args:
            sitemap_files: List of all sitemap file paths from all cores
            
        Returns:
            Path to the created global sitemap index file
        """
        # Use the configured output name (e.g., "sitemap.xml" or "sitemap_docs.xml")
        # Remove .xml extension if present, as _create_sitemap_index will add it
        base_name = self.config.output_name.replace('.xml', '').replace('.gz', '')
        return await self._create_sitemap_index(sitemap_files, base_name, is_global=True)
    
    async def _create_sitemap_index(self, sitemap_files: List[Path], core_name: str, is_global: bool = False) -> Path:
        """
        Create a sitemap index file referencing multiple sitemap files.
        
        Args:
            sitemap_files: List of sitemap file paths
            core_name: Name of the core (used for filename)
            is_global: If True, this is the global index for all cores
            
        Returns:
            Path to the created sitemap index file
        """
        # For global sitemap, use configured output name
        if is_global:
            index_filename = f"{core_name}.xml"
        else:
            index_filename = f"sitemap_index_{core_name}.xml"
        
        index_path = self.output_dir / index_filename
        
        # Create root element with namespace
        sitemapindex = Element('sitemapindex')
        sitemapindex.set('xmlns', 'http://www.sitemaps.org/schemas/sitemap/0.9')
        
        for sitemap_file in sitemap_files:
            sitemap_element = SubElement(sitemapindex, 'sitemap')
            
            # Add location
            loc = SubElement(sitemap_element, 'loc')
            if self.base_url:
                # Use absolute URL if base_url is configured
                loc.text = f"{self.base_url}/{sitemap_file.name}"
            else:
                # Use relative path
                loc.text = sitemap_file.name
            
            # Add last modification time (current time)
            lastmod = SubElement(sitemap_element, 'lastmod')
            lastmod.text = datetime.now().strftime('%Y-%m-%dT%H:%M:%S+00:00')
        
        # Convert to string with pretty formatting
        rough_string = tostring(sitemapindex, encoding='unicode')
        reparsed = minidom.parseString(rough_string)
        
        # Get pretty printed XML
        pretty_xml = reparsed.toprettyxml(indent="  ", encoding=None)
        lines = pretty_xml.split('\n')[1:]  # Skip XML declaration line
        
        # Add proper XML declaration and join lines
        xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>'
        xml_content = xml_declaration + '\n' + '\n'.join(line for line in lines if line.strip())
        
        # Write to file
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(xml_content)
        
        # Compress if requested
        if self.compress:
            compressed_path = await self._compress_file(index_path)
            index_path.unlink()  # Remove uncompressed file
            return compressed_path
        
        return index_path