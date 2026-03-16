cmake_minimum_required(VERSION 3.16)
project(pigskin C)

add_subdirectory(../genrecomp genrecomp_build)

file(GLOB RECOMP_SOURCES src/recomp/*.c)

add_executable(pigskin src/main.c ${RECOMP_SOURCES})

target_link_libraries(pigskin PRIVATE genrecomp genplusgx_hw)
target_include_directories(pigskin PRIVATE src/ ../genrecomp/include)
