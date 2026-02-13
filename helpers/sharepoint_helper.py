# config_sharepoint.py
from core.common_imports import *
from io import BytesIO
# from helpers.core_helper import *
# ===== Graph Client =====
class GraphClient:
    def __init__(self, client_id, client_secret, tenant_id, hostname, site_path, drive_name):
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id
        self.hostname = hostname
        self.site_path = site_path
        self.drive_name = drive_name
        self.token = None
        self.headers = None
        self.site_id = None
        self.drive_id = None

    def auth(self):
        app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=f"https://login.microsoftonline.com/{self.tenant_id}",
            client_credential=self.client_secret
        )
        result = app.acquire_token_for_client(SCOPES)

        # Debug: Print full token result
        print(f"🔑 Token Result Keys: {result.keys()}")
        if "error" in result:
            print(f"❌ Token Error: {result.get('error')}")
            print(f"❌ Error Description: {result.get('error_description')}")

        if "access_token" not in result:
            raise RuntimeError(f"❌ Could not acquire token: {result}")

        self.token = result["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
        print(f"✅ Token acquired successfully (length: {len(self.token)})")

    def resolve_site_and_drive(self):
        # Resolve site ID
        site_url = f"https://graph.microsoft.com/v1.0/sites/{self.hostname}:{self.site_path}"
        print(f"🔍 Requesting site URL: {site_url}")
        print(f"🔍 Hostname: {self.hostname}")
        print(f"🔍 Site Path: {self.site_path}")
        r = requests.get(site_url, headers=self.headers)
        print(f"🔍 Response Status: {r.status_code}")
        if r.status_code != 200:
            raise RuntimeError(f"❌ Resolve site failed: {r.status_code} {r.text}")
        self.site_id = r.json().get("id")
        if not self.site_id:
            raise RuntimeError("❌ site_id missing")

        # Resolve drive ID
        drives_url = f"https://graph.microsoft.com/v1.0/sites/{self.site_id}/drives"
        r = requests.get(drives_url, headers=self.headers)
        if r.status_code != 200:
            raise RuntimeError(f"❌ List drives failed: {r.status_code} {r.text}")
        for d in r.json().get("value", []):
            if d.get("name") == self.drive_name:
                self.drive_id = d.get("id")
                break
        if not self.drive_id:
            raise RuntimeError(f"❌ Drive '{self.drive_name}' not found")

    def _get_item_by_path(self, path):
        url = f"https://graph.microsoft.com/v1.0/sites/{self.site_id}/drives/{self.drive_id}/root:/{path}"
        return requests.get(url, headers=self.headers)

    def ensure_folder_path(self, folder_path):
        """Ensure nested folder path exists (e.g., 'RFP-logs/ALLRFPs/2025')."""
        segments = [seg.rstrip('.') for seg in folder_path.strip("/").split("/") if seg]
        current_path = ""
        parent_id = None

        for seg in segments:
            current_path = f"{current_path}/{seg}" if current_path else seg
            res = self._get_item_by_path(current_path)
            if res.status_code == 200:
                parent_id = res.json()["id"]
                continue
            elif res.status_code == 404:
                if parent_id:
                    create_url = f"https://graph.microsoft.com/v1.0/sites/{self.site_id}/drives/{self.drive_id}/items/{parent_id}/children"
                else:
                    create_url = f"https://graph.microsoft.com/v1.0/sites/{self.site_id}/drives/{self.drive_id}/root/children"
                payload = {
                    "name": seg,
                    "folder": {},
                    "@microsoft.graph.conflictBehavior": "replace"
                }
                cr = requests.post(create_url, headers={**self.headers, "Content-Type": "application/json"}, data=json.dumps(payload))
                if cr.status_code not in (200, 201):
                    raise RuntimeError(f"❌ Create folder '{seg}' failed: {cr.status_code} {cr.text}")
                parent_id = cr.json()["id"]
            else:
                raise RuntimeError(f"❌ Get path '{current_path}' failed: {res.status_code} {res.text}")
        return parent_id

    def upload_small_file(self, local_path, remote_path):
        """PUT /content for files <= 4 MB."""
        url = f"https://graph.microsoft.com/v1.0/sites/{self.site_id}/drives/{self.drive_id}/root:/{remote_path}:/content"
        with open(local_path, "rb") as f:
            r = requests.put(url, headers=self.headers, data=f)
        return r

    def upload_large_file(self, local_path, parent_folder_path, filename, chunk_size=5*1024*1024):
        """Upload >4MB via Upload Session."""
        parent_res = self._get_item_by_path(parent_folder_path)
        if parent_res.status_code != 200:
            raise RuntimeError(f"❌ Parent path not found before large upload: {parent_folder_path}")
        parent_id = parent_res.json()["id"]

        session_url = f"https://graph.microsoft.com/v1.0/sites/{self.site_id}/drives/{self.drive_id}/items/{parent_id}:/{filename}:/createUploadSession"
        sres = requests.post(session_url, headers={**self.headers, "Content-Type": "application/json"}, data=json.dumps({"item": {"@microsoft.graph.conflictBehavior": "replace"}}))
        if sres.status_code not in (200, 201):
            raise RuntimeError(f"❌ Create upload session failed: {sres.status_code} {sres.text}")
        upload_url = sres.json()["uploadUrl"]

        file_size = os.path.getsize(local_path)
        with open(local_path, "rb") as f:
            start = 0
            while start < file_size:
                end = min(start + chunk_size - 1, file_size - 1)
                f.seek(start)
                chunk = f.read(end - start + 1)
                headers = {
                    "Content-Length": str(end - start + 1),
                    "Content-Range": f"bytes {start}-{end}/{file_size}"
                }
                put = requests.put(upload_url, headers=headers, data=chunk)
                if put.status_code not in (200, 201, 202):
                    raise RuntimeError(f"❌ Chunk upload failed [{start}-{end}]: {put.status_code} {put.text}")
                start = end + 1
        return put

    def upload_file_as(self, local_path: str, remote_base_folder: str, dest_filename: str):
        """Upload a local file to SharePoint under remote_base_folder using dest_filename.
        Preserves original filenames when provided by callers.
        """
        if not self.token:
            self.auth()
        if not self.site_id or not self.drive_id:
            self.resolve_site_and_drive()

        remote_base_folder = remote_base_folder.rstrip("/")
        self.ensure_folder_path(remote_base_folder)

        size = os.path.getsize(local_path)
        if size <= 4 * 1024 * 1024:
            remote_path = f"{remote_base_folder}/{dest_filename}"
            return self.upload_small_file(local_path, remote_path)
        else:
            return self.upload_large_file(local_path, remote_base_folder, dest_filename)

    def sync_local_to_sharepoint(self, local_path, remote_base_folder):
        """Mirror a local file/folder into SharePoint under remote_base_folder."""
        if not self.token:
            self.auth()
        if not self.site_id or not self.drive_id:
            self.resolve_site_and_drive()

        self.ensure_folder_path(remote_base_folder)

        local_path = Path(local_path)
        if local_path.is_file():
            rel_remote_path = f"{remote_base_folder}/{local_path.name}"
            size = local_path.stat().st_size
            if size <= 4 * 1024 * 1024:
                res = self.upload_small_file(str(local_path), rel_remote_path)
            else:
                res = self.upload_large_file(str(local_path), remote_base_folder, local_path.name)
            return res

        for root, _, files in os.walk(local_path):
            for fname in files:
                fpath = Path(root) / fname
                rel = str(fpath.relative_to(local_path)).replace("\\", "/")
                parent_rel_folder = "/".join([p for p in [remote_base_folder, os.path.dirname(rel)] if p and p != "."])
                self.ensure_folder_path(parent_rel_folder)
                remote_file_path = f"{remote_base_folder}/{rel}".rstrip("/")
                size = fpath.stat().st_size
                if size <= 4 * 1024 * 1024:
                    res = self.upload_small_file(str(fpath), remote_file_path)
                else:
                    res = self.upload_large_file(str(fpath), parent_rel_folder, os.path.basename(rel))
                if res.status_code in (200, 201, 202):
                    print(f"☁️ Uploaded: {remote_file_path}")
                else:
                    print(f"❌ Upload failed: {remote_file_path} -> {res.status_code} {res.text}")

    def download_file_from_sharepoint(self, sp_path: str, local_path: str):
        """Download a file from SharePoint to local path."""
        url = f"https://graph.microsoft.com/v1.0/sites/{self.site_id}/drives/{self.drive_id}/root:/{sp_path}:/content"
        response = requests.get(url, headers=self.headers, stream=True)
        if response.status_code != 200:
            raise RuntimeError(f"❌ Download failed for {sp_path}: {response.status_code} {response.text}")

        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        print(f"☑️ Downloaded {sp_path} → {local_path}")
        return local_path

    def list_files_in_directory(self, sp_directory_path: str, file_extensions: list = None) -> list:
        """
        List all files in a SharePoint directory.

        Args:
            sp_directory_path: SharePoint directory path (e.g., 'RFP-logs/ALLRFPs/CompanyName')
            file_extensions: Optional list of file extensions to filter (e.g., ['.xls', '.xlsx'])

        Returns:
            List of file info dicts with 'name' and 'path' keys
        """
        url = f"https://graph.microsoft.com/v1.0/sites/{self.site_id}/drives/{self.drive_id}/root:/{sp_directory_path}:/children"
        response = requests.get(url, headers=self.headers)

        if response.status_code != 200:
            print(f"⚠️ Could not list directory {sp_directory_path}: {response.status_code}")
            return []

        files = []
        items = response.json().get('value', [])

        for item in items:
            name = item.get('name', '')
            is_folder = 'folder' in item

            if is_folder:
                # Recursively list files in subfolders
                subfolder_path = f"{sp_directory_path}/{name}"
                files.extend(self.list_files_in_directory(subfolder_path, file_extensions))
            else:
                # Check file extension if filter is provided
                if file_extensions:
                    if any(name.lower().endswith(ext.lower()) for ext in file_extensions):
                        files.append({
                            'name': name,
                            'path': f"{sp_directory_path}/{name}"
                        })
                else:
                    files.append({
                        'name': name,
                        'path': f"{sp_directory_path}/{name}"
                    })

        return files

    def list_folders_in_directory(self, sp_directory_path: str) -> list:
        """
        List immediate subfolders in a SharePoint directory (non-recursive).

        Args:
            sp_directory_path: SharePoint directory path (e.g., 'RFP-logs/ALLRFPs')

        Returns:
            List of folder info dicts with 'name' and 'path' keys
        """
        url = f"https://graph.microsoft.com/v1.0/sites/{self.site_id}/drives/{self.drive_id}/root:/{sp_directory_path}:/children"
        response = requests.get(url, headers=self.headers)

        if response.status_code != 200:
            print(f"⚠️ Could not list directory {sp_directory_path}: {response.status_code}")
            return []

        folders = []
        items = response.json().get('value', [])

        for item in items:
            if 'folder' in item:
                name = item.get('name', '')
                folders.append({
                    'name': name,
                    'path': f"{sp_directory_path}/{name}"
                })

        return folders

    def download_rfp_files_from_sharepoint(self, company_name: str, local_output_dir: str, sp_base_folder: str) -> list:
        """
        Download all RFP Excel files from SharePoint for a given company.

        Args:
            company_name: Company name to fetch RFPs for
            local_output_dir: Local directory to save files (e.g., OUTPUT_DIR)
            sp_base_folder: SharePoint base folder (e.g., 'RFP-logs')

        Returns:
            List of downloaded file paths
        """
        import re
        safe_company_name = re.sub(r'[<>:"/\\|?*]', '_', company_name).strip().rstrip('.')
        sp_company_path = f"{sp_base_folder}/ALLRFPs/{safe_company_name}"

        print(f"🔄 Fetching RFP files from SharePoint: {sp_company_path}")

        # List all Excel files in the company's folder
        excel_files = self.list_files_in_directory(sp_company_path, ['.xls', '.xlsx'])

        if not excel_files:
            print(f"⚠️ No Excel files found in SharePoint: {sp_company_path}")
            return []

        downloaded_files = []
        for file_info in excel_files:
            sp_path = file_info['path']
            file_name = file_info['name']

            # Determine local path based on SharePoint structure
            # SP: RFP-logs/ALLRFPs/CompanyName/RFP_title/downloaded-rfp/file.xls
            # Local: OUTPUT_DIR/CompanyName/RFP_title/downloaded-rfp/file.xls
            relative_path = sp_path.replace(f"{sp_base_folder}/ALLRFPs/", "")
            local_path = os.path.join(local_output_dir, relative_path)

            try:
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                self.download_file_from_sharepoint(sp_path, local_path)
                downloaded_files.append(local_path)
                print(f"✅ Downloaded: {file_name}")
            except Exception as e:
                print(f"⚠️ Failed to download {file_name}: {e}")

        print(f"📥 Downloaded {len(downloaded_files)} RFP files from SharePoint")
        return downloaded_files

    def get_file_content_from_sharepoint(self, sp_path: str):
        """Fetch a file from SharePoint with fuzzy path matching."""
        
        # Define normalize_filename locally to completely avoid circular import
        def normalize_filename(name: str) -> str:
            """Normalize filename by removing non-alphanumeric characters and converting to lowercase"""
            import re
            return re.sub(r'[^a-z0-9]', '', name.lower())
        
        print(f"\n🔍 SharePoint Fuzzy File Search")
        print(f"   📄 Requested: '{sp_path}'")
        
        # Split path into directory and filename
        path_parts = sp_path.split('/')
        if len(path_parts) < 2:
            # If no directory structure, try direct access
            url = f"https://graph.microsoft.com/v1.0/sites/{self.site_id}/drives/{self.drive_id}/root:/{sp_path}:/content"
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200:
                content = BytesIO(response.content)
                content.seek(0)
                return content
            else:
                raise RuntimeError(f"❌ File not found: {sp_path}")
        
        directory_path = '/'.join(path_parts[:-1])
        target_filename = path_parts[-1]
        
        print(f"Directory: '{directory_path}'")
        print(f"Target: '{target_filename}'")
        print(f"Normalized: '{normalize_filename(target_filename)}'")
        
        try:
            # List files in directory
            dir_url = f"https://graph.microsoft.com/v1.0/sites/{self.site_id}/drives/{self.drive_id}/root:/{directory_path}:/children"
            dir_response = requests.get(dir_url, headers=self.headers)
            
            if dir_response.status_code != 200:
                print(f"   ❌ Directory access failed: {dir_response.status_code}")
                raise RuntimeError(f"❌ Cannot access directory: {directory_path}")
            
            files = dir_response.json().get('value', [])
            print(f"   📊 Directory contains {len(files)} items")
            
            # Normalize target for comparison
            normalized_target = normalize_filename(target_filename)
            
            # Strategy 1: Try exact filename match first
            for file in files:
                if file.get('name') == target_filename:
                    print(f"   ✅ Exact match found: '{target_filename}'")
                    actual_path = sp_path
                    break
                else:
                    # Strategy 2: Try normalized matching
                    actual_path = None
                    for file in files:
                        file_name = file.get('name', '')
                        if normalize_filename(file_name) == normalized_target:
                            print(f"   ✅ Normalized match found!")
                            print(f"      Target: '{target_filename}' → '{normalized_target}'")
                            print(f"      Found:  '{file_name}' → '{normalize_filename(file_name)}'")
                            actual_path = f"{directory_path}/{file_name}"
                            break
                    
                    if not actual_path:
                        # Strategy 3: Try partial matching
                        partial_matches = []
                        for file in files:
                            file_name = file.get('name', '')
                            norm_file = normalize_filename(file_name)
                            if normalized_target in norm_file or norm_file in normalized_target:
                                partial_matches.append(file_name)
                        
                        if partial_matches:
                            actual_path = f"{directory_path}/{partial_matches[0]}"
                            print(f"   ✅ Partial match found: '{partial_matches[0]}'")
                        else:
                            # Show available files for debugging
                            print(f"   ❌ No match found. Available files:")
                            for i, file in enumerate(files[:10]):
                                name = file.get('name', 'Unknown')
                                norm = normalize_filename(name)
                                print(f"      {i+1}. '{name}' → '{norm}'")
                            
                            raise RuntimeError(f"❌ File not found: {target_filename}")
                    
            # Fetch the file using the determined path
            print(f"   �� Fetching: {actual_path}")
            url = f"https://graph.microsoft.com/v1.0/sites/{self.site_id}/drives/{self.drive_id}/root:/{actual_path}:/content"
            response = requests.get(url, headers=self.headers)
            
            if response.status_code == 200:
                print(f"   ✅ Success! ({len(response.content)} bytes)")
                content = BytesIO(response.content)
                content.seek(0)
                return content
            else:
                raise RuntimeError(f"❌ Fetch failed: {response.status_code} {response.text}")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
            raise e

    def find_file_with_fuzzy_matching(self, sp_path: str):
        """
        Find a file in SharePoint using fuzzy matching for filename normalization
        Returns the exact path of the found file, or None if not found
        """
        # Define normalize_filename locally to completely avoid circular import
        def normalize_filename(name: str) -> str:
            """Normalize filename by removing non-alphanumeric characters and converting to lowercase"""
            import re
            return re.sub(r'[^a-z0-9]', '', name.lower())
        
        # Split the path into directory and filename
        path_parts = sp_path.split('/')
        if len(path_parts) < 2:
            return sp_path  # If no directory structure, return as-is
        
        directory_path = '/'.join(path_parts[:-1])
        target_filename = path_parts[-1]
        
        print(f"Fuzzy file search:")
        print(f"Directory: '{directory_path}'")
        print(f"Target file: '{target_filename}'")
        print(f"Normalized target: '{normalize_filename(target_filename)}'")
        
        try:
            # List files in the directory
            dir_url = f"https://graph.microsoft.com/v1.0/sites/{self.site_id}/drives/{self.drive_id}/root:/{directory_path}:/children"
            response = requests.get(dir_url, headers=self.headers)
            
            if response.status_code != 200:
                print(f"   ❌ Cannot access directory: {response.status_code}")
                return sp_path  # Return original path if directory check fails
            
            files = response.json().get('value', [])
            print(f"   📊 Found {len(files)} files in directory")
            
            # Normalize the target filename for comparison
            normalized_target = normalize_filename(target_filename)
            
            # Look for exact matches first
            for file in files:
                file_name = file.get('name', '')
                if file_name == target_filename:
                    print(f"   ✅ Exact match found: '{file_name}'")
                    return sp_path
            
            # If no exact match, look for normalized matches
            print(f"   🔍 No exact match, trying fuzzy matching...")
            for file in files:
                file_name = file.get('name', '')
                normalized_file = normalize_filename(file_name)
                
                if normalized_file == normalized_target:
                    print(f"   ✅ Fuzzy match found!")
                    print(f"      Target: '{target_filename}' → '{normalized_target}'")
                    print(f"      Found:  '{file_name}' → '{normalized_file}'")
                    
                    # Return the correct path with the actual filename
                    correct_path = f"{directory_path}/{file_name}"
                    return correct_path
            
            # If still no match, look for partial matches (target contained in filename)
            print(f"   🔍 No exact fuzzy match, trying partial matching...")
            partial_matches = []
            for file in files:
                file_name = file.get('name', '')
                normalized_file = normalize_filename(file_name)
                
                if normalized_target in normalized_file or normalized_file in normalized_target:
                    partial_matches.append((file_name, normalized_file))
            
            if partial_matches:
                print(f"   📋 Found {len(partial_matches)} partial matches:")
                for file_name, normalized in partial_matches:
                    print(f"      - '{file_name}' → '{normalized}'")
                
                # Use the first partial match
                best_match = partial_matches[0][0]
                print(f"   ✅ Using best partial match: '{best_match}'")
                correct_path = f"{directory_path}/{best_match}"
                return correct_path
            
            print(f"   ❌ No matching file found")
            return None
            
        except Exception as e:
            print(f"   ❌ Error during fuzzy search: {e}")
            return sp_path  # Return original path if search fails