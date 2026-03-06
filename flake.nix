{
  description = "Python project";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils, ... }:
    flake-utils.lib.eachDefaultSystem (system: let
      pkgs = import nixpkgs { inherit system; };
      runtimeLibs = with pkgs; [
        stdenv.cc.cc.lib
      ];
      packages = with pkgs; [
        python3
        python3Packages.pip
        python3Packages.virtualenv
      ] ++ runtimeLibs;
    in {
      devShells.default = pkgs.mkShell {
        buildInputs = packages;
        LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath runtimeLibs;
      };
    });
}