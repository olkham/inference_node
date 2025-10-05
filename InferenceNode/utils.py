"""
Utility functions for InferenceNode
"""
import re
import logging


def parse_windows_platform(platform_string: str) -> str:
    """
    Parse Windows platform string to readable format.
    
    Args:
        platform_string: Platform string from platform.platform()
        
    Returns:
        Human-readable Windows version string
        
    Examples:
        >>> parse_windows_platform("Windows-10-10.0.26100-SP0")
        'Windows 11 Version 24H2 (2024 Update)'
        >>> parse_windows_platform("Linux-5.15.0-88-generic-x86_64")
        'Linux-5.15.0-88-generic-x86_64'
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Windows version mapping
        windows_versions = {
            "6.1.7600": "Windows 7",
            "6.1.7601": "Windows 7 with Service Pack 1",
            "6.2.9200": "Windows 8",
            "6.3.9200": "Windows 8.1",
            "6.3.9600": "Windows 8.1 with Update 1",
            "10.0.10240": "Windows 10 Version 1507",
            "10.0.10586": "Windows 10 Version 1511 (November Update)",
            "10.0.14393": "Windows 10 Version 1607 (Anniversary Update)",
            "10.0.15063": "Windows 10 Version 1703 (Creators Update)",
            "10.0.16299": "Windows 10 Version 1709 (Fall Creators Update)",
            "10.0.17134": "Windows 10 Version 1803 (April 2018 Update)",
            "10.0.17763": "Windows 10 Version 1809 (October 2018 Update)",
            "10.0.18362": "Windows 10 Version 1903 (May 2019 Update)",
            "10.0.18363": "Windows 10 Version 1909 (November 2019 Update)",
            "10.0.19041": "Windows 10 Version 2004 (May 2020 Update)",
            "10.0.19042": "Windows 10 Version 20H2 (October 2020 Update)",
            "10.0.19043": "Windows 10 Version 21H1 (May 2021 Update)",
            "10.0.19044": "Windows 10 Version 21H2 (November 2021 Update)",
            "10.0.19045": "Windows 10 Version 22H2 (2022 Update)",
            "10.0.20348": "Windows Server 2022 Version 21H2",
            "10.0.22000": "Windows 11 Version 21H2 (original release)",
            "10.0.22621": "Windows 11 Version 22H2 (2022 Update)",
            "10.0.22631": "Windows 11 Version 23H2 (2023 Update)",
            "10.0.26100": "Windows 11 Version 24H2 (2024 Update)"
        }
        
        # Check if this is a Windows platform string
        if not platform_string.startswith("Windows"):
            return platform_string
        
        # Extract version number from platform string
        # Format: Windows-10-10.0.26100-SP0
        version_match = re.search(r'(\d+\.\d+\.\d+)', platform_string)
        
        if version_match:
            version = version_match.group(1)
            readable_version = windows_versions.get(version)
            
            if readable_version:
                # Check if it's a server version based on platform string
                if "Server" in platform_string or any(server_indicator in platform_string.lower() 
                                                     for server_indicator in ["datacenter", "standard", "enterprise"]):
                    # Handle server versions
                    if version == "6.1.7600" or version == "6.1.7601":
                        return "Windows Server 2008 R2" + (" with Service Pack 1" if version == "6.1.7601" else "")
                    elif version == "6.2.9200":
                        return "Windows Server 2012"
                    elif version == "6.3.9200" or version == "6.3.9600":
                        return "Windows Server 2012 R2"
                    elif version == "10.0.14393":
                        return "Windows Server 2016"
                    elif version == "10.0.17763":
                        return "Windows Server 2019"
                    elif version == "10.0.20348":
                        return "Windows Server 2022 Version 21H2"
                
                return readable_version
        
        # If no match found, return original string
        return platform_string
        
    except Exception as e:
        logger.debug(f"Platform parsing failed: {str(e)}")
        return platform_string


if __name__ == "__main__":
    # Simple test
    logging.basicConfig(level=logging.INFO)
    
    test_cases = [
        "Windows-10-10.0.26100-SP0",
        "Windows-10-10.0.22621-SP0",
        "Windows-10-10.0.19045-SP0",
        "Linux-5.15.0-88-generic-x86_64",
        "Darwin-23.1.0-arm64-arm-64bit"
    ]
    
    print("Testing parse_windows_platform function:")
    print("-" * 60)
    for test in test_cases:
        result = parse_windows_platform(test)
        print(f"Input:  {test}")
        print(f"Output: {result}")
        print()
