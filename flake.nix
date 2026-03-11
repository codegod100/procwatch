{
  description = "Process Watcher TUI - Interactive process monitor with search and sorting";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils, ... }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};

        # Python with required packages
        pythonEnv = pkgs.python3.withPackages (ps: with ps; [
          psutil
          textual
        ]);

        # The application package
        procwatch = pkgs.stdenv.mkDerivation {
          pname = "procwatch";
          version = "0.1.0";

          src = ./.;

          buildInputs = [ pythonEnv ];

          installPhase = ''
            mkdir -p $out/bin
            cp procwatch.py $out/bin/procwatch
            chmod +x $out/bin/procwatch
            # Patch shebang to use the nix store python
            patchShebangs $out/bin/procwatch
          '';

          meta = with pkgs.lib; {
            description = "Process Watcher TUI - Interactive process monitor with search and sorting";
            mainProgram = "procwatch";
            platforms = platforms.unix;
          };
        };

      in {
        packages = {
          default = procwatch;
          procwatch = procwatch;
        };

        devShells.default = pkgs.mkShell {
          buildInputs = [
            pythonEnv
            pkgs.python3Packages.pip  # For additional development installs
          ];

          shellHook = ''
            echo "Process Watcher development environment"
            echo "Run with: python procwatch.py"
          '';
        };

        apps.default = {
          type = "app";
          program = "${procwatch}/bin/procwatch";
        };
      }
    );
}